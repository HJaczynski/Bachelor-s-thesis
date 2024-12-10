import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
import torch
from tqdm import tqdm
from sklearn.cluster import KMeans

def extract_average_color(image):
    
    image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    image = cv2.resize(image, (32, 32))
    
    # Compute the mean color which is important for team assignment 
    mean_color = image.mean(axis=(0, 1)) 
    return mean_color

def classify_player(dominant_color, team_colors):
    # Compute distances to each team color centroid
    distances = np.linalg.norm(team_colors - dominant_color, axis=1)
    # Assign goalkeeper to the closest team
    team_id = np.argmin(distances)
    return team_id

def get_center(box):
    # box format: [x_min, y_min, x_max, y_max] for ball possesion 
    x_center = (box[0] + box[2]) / 2
    y_center = (box[1] + box[3]) / 2
    return np.array([x_center, y_center])

def resolve_goalkeepers_team_id(players, goalkeepers):
    if len(goalkeepers) == 0 or len(players) == 0:
        return np.array([])
    goalkeepers_xy = goalkeepers.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
    players_xy = players.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
    team_0_players = players_xy[np.array(players.class_id) == 0]
    team_1_players = players_xy[np.array(players.class_id) == 1]
    team_0_centroid = team_0_players.mean(axis=0) if len(team_0_players) > 0 else np.array([0, 0])
    team_1_centroid = team_1_players.mean(axis=0) if len(team_1_players) > 0 else np.array([0, 0])
    goalkeepers_team_id = []
    for goalkeeper_xy in goalkeepers_xy:
        dist_0 = np.linalg.norm(goalkeeper_xy - team_0_centroid)
        dist_1 = np.linalg.norm(goalkeeper_xy - team_1_centroid)
        if dist_0 == dist_1:
            # Assign to a default team if equidistant
            goalkeepers_team_id.append(0)
        else:
            goalkeepers_team_id.append(0 if dist_0 < dist_1 else 1)
    return np.array(goalkeepers_team_id)

def load_model(model_path, device):
    model = YOLO(model_path)
    model.to(device)
    return model

def extract_team_colors(video_path, model, device, stride=30, max_frames=10):
    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    PLAYER_ID = 2

    initial_frames = []
    # Collect frames at intervals to sample player colors
    for idx in range(0, frame_count, stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        initial_frames.append(frame)
        if len(initial_frames) >= max_frames:
            break

    # Collect dominant colors from initial frames
    dominant_colors = []
    print("Collecting dominant colors from initial frames...")
    for frame in tqdm(initial_frames):
        results = model(frame, device=device)
        result = results[0]
        detections = sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int)
        )
        players_detections = detections[detections.class_id == PLAYER_ID]
        for xyxy in players_detections.xyxy:
            crop = sv.crop_image(frame, xyxy)
            color = extract_average_color(crop)
            dominant_colors.append(color)

    # Cluster the dominant colors to find team colors
    print("Clustering colors to identify team colors...")
    dominant_colors = np.array(dominant_colors)
    kmeans = KMeans(n_clusters=2, random_state=42)
    kmeans.fit(dominant_colors)
    team_colors = kmeans.cluster_centers_

    cap.release()
    return team_colors

def process_batch(frames, model, device, team_colors, ellipse_annotator, triangle_annotator,
                  out, POSSESSION_THRESHOLD, BALL_ID, GOALKEEPER_ID, PLAYER_ID, REFEREE_ID,
                  team_0_possession_frames, team_1_possession_frames):
    # Run YOLO inference on batch
    results = model(frames, device=device)

    for i, result in enumerate(results):
        detections = sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int)
        )

        # Separate detections by classes
        ball_detections = detections[detections.class_id == BALL_ID]
        ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)
        all_detections = detections[detections.class_id != BALL_ID]

        # Apply Non-Maximum Suppression
        all_detections = all_detections.with_nms(threshold=0.5, class_agnostic=True)

        # Separate player, goalkeeper, and referee detections
        goalkeepers_detections = all_detections[all_detections.class_id == GOALKEEPER_ID]
        players_detections = all_detections[all_detections.class_id == PLAYER_ID]
        referees_detections = all_detections[all_detections.class_id == REFEREE_ID]

        # Extract crops and classify players by team
        team_ids = []
        for xyxy in players_detections.xyxy:
            crop = sv.crop_image(frames[i], xyxy)
            dominant_color = extract_average_color(crop)
            team_id = classify_player(dominant_color, team_colors)
            team_ids.append(team_id)

        
        # Assign team IDs to player detections
        players_detections.class_id = np.array(team_ids)

        # Assign team IDs to goalkeepers
        goalkeepers_detections.class_id = resolve_goalkeepers_team_id(players_detections, goalkeepers_detections)

        # Merge detections
        all_detections = sv.Detections.merge([players_detections, goalkeepers_detections, referees_detections])

        # Determine ball possession
        if len(ball_detections) > 0 and len(players_detections) > 0:
            ball_center = get_center(ball_detections.xyxy[0])
            player_centers = np.array([get_center(box) for box in players_detections.xyxy])
            distances = np.linalg.norm(player_centers - ball_center, axis=1)
            min_dist_idx = np.argmin(distances)
            min_dist = distances[min_dist_idx]

            if min_dist < POSSESSION_THRESHOLD:
                ball_holder_team_id = players_detections.class_id[min_dist_idx]
                if ball_holder_team_id == 0:
                    team_0_possession_frames += 1
                elif ball_holder_team_id == 1:
                    team_1_possession_frames += 1

        frame_bgr = cv2.cvtColor(frames[i], cv2.COLOR_RGB2BGR)
        annotated_frame = ellipse_annotator.annotate(
            scene=frame_bgr,
            detections=all_detections
        )
        annotated_frame = triangle_annotator.annotate(
            scene=annotated_frame,
            detections=ball_detections
        )
        out.write(annotated_frame)

    return team_0_possession_frames, team_1_possession_frames

def process_video(video_path, output_path, model, device, team_colors):
    BALL_ID = 0
    GOALKEEPER_ID = 1
    PLAYER_ID = 2
    REFEREE_ID = 3

    # Annotators
    ellipse_annotator = sv.EllipseAnnotator(
        color=sv.ColorPalette.from_hex(['#00BFFF', '#FF1493', '#FFD700']),
        thickness=2
    )
    #in this scenario we don't use labels 
    label_annotator = sv.LabelAnnotator(
        color=sv.ColorPalette.from_hex(['#00BFFF', '#FF1493', '#FFD700']),
        text_color=sv.Color.from_hex('#000000'),
        text_position=sv.Position.BOTTOM_CENTER
    )
    triangle_annotator = sv.TriangleAnnotator(
        color=sv.Color.from_hex('#FFD700'),
        base=25,
        height=21,
        outline_thickness=1
    )

    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

    team_0_possession_frames = 0
    team_1_possession_frames = 0

    # Threshold for possession (distance in pixels) from player to ball 
    POSSESSION_THRESHOLD = 50

    frames = []
    batch_size = 16

    print("Processing video and classifying players...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(frame_rgb)

        if len(frames) == batch_size:
            team_0_possession_frames, team_1_possession_frames = process_batch(
                frames, model, device, team_colors,
                ellipse_annotator, triangle_annotator,
                out, POSSESSION_THRESHOLD, BALL_ID, GOALKEEPER_ID, PLAYER_ID, REFEREE_ID,
                team_0_possession_frames, team_1_possession_frames
            )
            frames = []

    
    if len(frames) > 0:
        team_0_possession_frames, team_1_possession_frames = process_batch(
            frames, model, device, team_colors,
            ellipse_annotator, triangle_annotator,
            out, POSSESSION_THRESHOLD, BALL_ID, GOALKEEPER_ID, PLAYER_ID, REFEREE_ID,
            team_0_possession_frames, team_1_possession_frames
        )

    cap.release()
    out.release()

    # Calculate ball possession percentages
    total_possession_frames = team_0_possession_frames + team_1_possession_frames
    if total_possession_frames > 0:
        team_0_possession_percent = (team_0_possession_frames / total_possession_frames) * 100
        team_1_possession_percent = (team_1_possession_frames / total_possession_frames) * 100
    else:
        team_0_possession_percent = 0
        team_1_possession_percent = 0

    return team_0_possession_percent, team_1_possession_percent

def analyze_video_model(video_path, output_path, model_path="models/player_detection.pt"):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"DECIVCE TYPE: {device}")
    model = load_model(model_path, device)
    team_colors = extract_team_colors(video_path, model, device)

    team_0_possession_percent, team_1_possession_percent = process_video(
        video_path, output_path, model, device, team_colors
    )

    print("Processing complete. Output video saved to:", output_path)
    print(f"Team 0 Possession: {team_0_possession_percent:.2f}%")
    print(f"Team 1 Possession: {team_1_possession_percent:.2f}%")

    return team_0_possession_percent, team_1_possession_percent

