import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
import torch
from tqdm import tqdm
from sklearn.cluster import KMeans
from sklearn.cluster import AgglomerativeClustering
from sklearn.linear_model import RANSACRegressor
from concurrent.futures import ThreadPoolExecutor
from sports.annotators.soccer import draw_pitch, draw_points_on_pitch, draw_pitch_voronoi_diagram
from sports.configs.soccer import SoccerPitchConfiguration
from sports.common.view import ViewTransformer
import pandas as pd
from collections import defaultdict, deque
import os


CONFIG = SoccerPitchConfiguration()

class PositionSmoother:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.last_positions = {}  # key: object_id, val: (x, y)

    def smooth(self, object_id, current_position):
        if object_id not in self.last_positions:
            self.last_positions[object_id] = current_position
            return current_position

        old_x, old_y = self.last_positions[object_id]
        x, y = current_position
        new_x = self.alpha * x + (1 - self.alpha) * old_x
        new_y = self.alpha * y + (1 - self.alpha) * old_y

        self.last_positions[object_id] = (new_x, new_y)
        return (new_x, new_y)

ball_smoother = PositionSmoother(alpha=0.5)

def extract_average_color(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    image = cv2.resize(image, (32, 32))
    mean_color = image.mean(axis=(0, 1))
    return mean_color

def classify_player(dominant_color, team_colors):
    distances = np.linalg.norm(team_colors - dominant_color, axis=1)
    team_id = np.argmin(distances)
    return team_id

def get_center(box):
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
        goalkeepers_team_id.append(0 if dist_0 <= dist_1 else 1)

    return np.array(goalkeepers_team_id)

def load_model(model_path, device):
    model = YOLO(model_path)
    model.to(device)
    return model

def run_yolo_model(frames, model, device):
    return model(frames, device=device)

def run_keypoint_model(frames, key_point_model, device):
    return key_point_model(frames, device=device)

def run_simultaneous_inference(frames, yolo_model, key_point_model, device):
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_yolo = executor.submit(run_yolo_model, frames, yolo_model, device)
        future_keypoints = executor.submit(run_keypoint_model, frames, key_point_model, device)
        
        results_yolo = future_yolo.result()
        results_keypoints = future_keypoints.result()
    
    return results_yolo, results_keypoints

def extract_team_colors(video_path, model, device, stride=30, max_frames=10):
    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    PLAYER_ID = 2

    initial_frames = []
    for idx in range(0, frame_count, stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        initial_frames.append(frame)
        if len(initial_frames) >= max_frames:
            break

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

    print("Clustering colors to identify team colors...")
    dominant_colors = np.array(dominant_colors)
    kmeans = KMeans(n_clusters=2, random_state=42)
    kmeans.fit(dominant_colors)
    team_colors = kmeans.cluster_centers_

    cap.release()
    return team_colors

def process_batch(
    frames,
    model,
    key_point_model,
    device,
    team_colors,
    POSSESSION_THRESHOLD,
    BALL_ID,
    GOALKEEPER_ID,
    PLAYER_ID,
    REFEREE_ID,
    triangle_annotator=None,
    ellipse_annotator=None,
    label_annotator=None,
    ball_annotator=None,
    out=None,
    team_0_possession_frames=0,
    team_1_possession_frames=0,
    last_player_positions=None,       # not strictly needed if we use ByteTrack
    fps=30,
    tracker=None,                     # ByteTrack instance
    speed_buffer=None,
    ball_speed_buffer=None,          # dict[track_id -> deque of last N real positions]
    homography_conf_threshold=0.8     # min confidence for using a keypoint as reference
):
    """
    Processes a batch of frames:
     - Runs YOLO & keypoint detection
     - Determines ball possession
     - Tracks players with ByteTrack
     - Applies perspective transform to get real distances
     - Averages last N frames to compute speed in km/h
     - Computes average speed for each team and the ball
     - Computes total distance covered by each team and the ball
    """

    if last_player_positions is None:
        last_player_positions = []

    if tracker is None:
        # fallback if not provided
        tracker = sv.ByteTrack()
        tracker.reset()

    if speed_buffer is None:
        # fallback if not provided
        speed_buffer = defaultdict(lambda: deque(maxlen=2))  # Only need last position for distance

    if ball_speed_buffer is None:
        # fallback if not provided
        ball_speed_buffer = defaultdict(lambda: deque(maxlen=2))  # Only need last position for distance

    # Initialize lists to accumulate speeds for each team and the ball
    all_player_speeds_team0 = []
    all_player_speeds_team1 = []
    all_ball_speeds = []

    # Initialize total distance accumulators (in meters)
    total_distance_team0 = 0.0
    total_distance_team1 = 0.0
    total_distance_ball = 0.0

    # 1) Run detection + keypoint model
    results, results_keypoints = run_simultaneous_inference(frames, model, key_point_model, device)

    frame_data = []

    for i, (result, result_kpts) in enumerate(zip(results, results_keypoints)):
        # ------------------------------------------------------------
        # Convert YOLO result to Supervision Detections
        # ------------------------------------------------------------
        detections = sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int)
        )

        # Convert YOLO keypoints to Supervision KeyPoints
        kp_detections = sv.KeyPoints.from_ultralytics(result_kpts)

        # ---------------------------
        # Compute Homography / Transform
        # ---------------------------
        if kp_detections.xy is not None and len(kp_detections.xy) > 0:
            frame_ref_points = []
            pitch_ref_points = []
            if kp_detections.xy[0].shape[0] == len(CONFIG.vertices):
                confidence_mask = kp_detections.confidence[0] >= homography_conf_threshold
                frame_ref_points = kp_detections.xy[0][confidence_mask]
                pitch_ref_points = np.array(CONFIG.vertices)[confidence_mask] / 100.0
            else:
                frame_ref_points = []
                pitch_ref_points = []

            if len(frame_ref_points) >= 4:
                transformer = ViewTransformer(frame_ref_points, pitch_ref_points)
            else:
                transformer = lambda pts: pts
        else:
            transformer = lambda pts: pts

        # ------------------------------------------------------------
        # Separate ball from other detections
        # ------------------------------------------------------------
        ball_detections = detections[detections.class_id == BALL_ID]
        ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

        # Everything else
        all_detections = detections[detections.class_id != BALL_ID]
        all_detections = all_detections.with_nms(threshold=0.5, class_agnostic=True)

        # Separate groups
        goalkeepers_detections = all_detections[all_detections.class_id == GOALKEEPER_ID]
        players_detections = all_detections[all_detections.class_id == PLAYER_ID]
        referees_detections = all_detections[all_detections.class_id == REFEREE_ID]

        # Classify players into team 0 or 1
        team_ids = []
        for xyxy in players_detections.xyxy:
            crop = sv.crop_image(frames[i], xyxy)
            dominant_color = extract_average_color(crop)
            team_id = classify_player(dominant_color, team_colors)
            team_ids.append(team_id)
        players_detections.class_id = np.array(team_ids)

        # Resolve GK
        goalkeepers_detections.class_id = resolve_goalkeepers_team_id(players_detections, goalkeepers_detections)

        # Merge them all
        all_detections = sv.Detections.merge([players_detections, goalkeepers_detections, referees_detections])

        # ------------------------------------------------------------
        # Track with ByteTrack -> stable .tracker_id
        # ------------------------------------------------------------
        all_detections = tracker.update_with_detections(detections=all_detections)

        # ------------------------------------------------------------
        # Ball Possession Logic
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # Speed and Distance Calculation in Real Coordinates => KM/H & Meters
        # ------------------------------------------------------------
        # Only for players (class_id == 0,1)
        speed_detections = all_detections[np.isin(all_detections.class_id, [0, 1])]
        current_positions_px = speed_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)

        # Transform from pixel => pitch coords (assumed meters)
        current_positions_m = transformer.transform_points(current_positions_px)

        speeds_kmh = []
        for track_id, (mx, my), team_id in zip(speed_detections.tracker_id, current_positions_m, speed_detections.class_id):
            # Some detections might have track_id == -1 if not tracked
            if track_id == -1:
                speed_kmh = 0.0
                speeds_kmh.append(speed_kmh)
                continue

            # Calculate distance covered since last position
            if len(speed_buffer[track_id]) >= 1:
                prev_mx, prev_my = speed_buffer[track_id][-1]
                distance_m = np.hypot(mx - prev_mx, my - prev_my)
                if team_id == 0:
                    total_distance_team0 += distance_m
                elif team_id == 1:
                    total_distance_team1 += distance_m

            # Append new real-world position to the buffer for both speed and distance calculations
            speed_buffer[track_id].append((mx, my))

            # Speed calculation
            if len(speed_buffer[track_id]) >= 2:
                (mx_old, my_old) = speed_buffer[track_id][0]  # oldest in buffer
                (mx_new, my_new) = speed_buffer[track_id][-1] # newest
                dist_m = np.hypot(mx_new - mx_old, my_new - my_old)

                # frames spanned in the buffer
                frame_intervals = len(speed_buffer[track_id]) - 1

                # speed in m/s
                speed_m_s = dist_m * (fps / frame_intervals)
                # convert to km/h
                speed_kmh = speed_m_s * 3.6
            else:
                speed_kmh = 0.0

            speeds_kmh.append(speed_kmh)

            # Accumulate player speeds based on team
            if team_id == 0:
                all_player_speeds_team0.append(speed_kmh)
            elif team_id == 1:
                all_player_speeds_team1.append(speed_kmh)

        # Build labels
        labels = [f"{s:.1f} km/h" for s in speeds_kmh]

        frame_bgr = cv2.cvtColor(frames[i], cv2.COLOR_RGB2BGR)
        # ------------------------------------------------------------
        # Ball speed and distance calculation
        # ------------------------------------------------------------
        if len(ball_detections) > 0:
            # Sort by confidence descending (or pick argmax)
            sorted_indices = np.argsort(-ball_detections.confidence)
            best_index = sorted_indices[0]  # index of highest confidence ball
            best_ball = ball_detections[best_index:best_index+1]  # slice with one detection
            
            ball_detections_speed = best_ball.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            ball_positions_m = transformer.transform_points(ball_detections_speed)
            
            if len(ball_positions_m) > 0:
                # Calculate distance covered since last position
                if len(ball_speed_buffer[0]) >= 1:
                    prev_ball_mx, prev_ball_my = ball_speed_buffer[0][-1]
                    ball_distance_m = np.hypot(ball_positions_m[0][0] - prev_ball_mx, ball_positions_m[0][1] - prev_ball_my)
                    total_distance_ball += ball_distance_m

                # Append current position to ball speed buffer
                ball_speed_buffer[0].append(ball_positions_m[0])

                # Speed calculation
                if len(ball_speed_buffer[0]) >= 2:
                    (mx_old, my_old) = ball_speed_buffer[0][0]
                    (mx_new, my_new) = ball_speed_buffer[0][-1]
                    dist_m = np.hypot(mx_new - mx_old, my_new - my_old)
                    frame_intervals = len(ball_speed_buffer[0]) - 1
                    speed_m_s = dist_m * (fps / frame_intervals)
                    speed_kmh = speed_m_s * 3.6
                else:
                    speed_kmh = 0.0
                
                # Accumulate ball speeds
                all_ball_speeds.append(speed_kmh)
                
                # Single label for the single detection
                ball_label = [f"Ball: {speed_kmh:.1f} km/h"]
                
                # Annotate using just one box and one label
                annotated_frame = ball_annotator.annotate(
                    scene=frame_bgr, 
                    detections=best_ball, 
                    labels=ball_label
                )
            else:
                # No positions => no speed label
                annotated_frame = frame_bgr
        else:
            # No ball at all
            annotated_frame = frame_bgr


        # ------------------------------------------------------------
        # Annotate Frame
        # ------------------------------------------------------------
        
        annotated_frame = ellipse_annotator.annotate(scene=annotated_frame, detections=all_detections)
        annotated_frame = triangle_annotator.annotate(scene=annotated_frame, detections=ball_detections)
        

        if label_annotator is not None:
            annotated_frame = label_annotator.annotate(
                scene=annotated_frame,
                detections=speed_detections,
                labels=labels
            )

        out.write(annotated_frame)

        # ------------------------------------------------------------
        # Collect data for downstream usage
        # ------------------------------------------------------------
        frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_data = {
            'keypoints': kp_detections,
            'ball': frame_ball_xy,
            'players': players_detections,
            'referees': referees_detections
        }
        frame_data.append(pitch_data)

    # ------------------------------------------------------------
    # Compute Average Speeds
    # ------------------------------------------------------------
    if all_player_speeds_team0:
        average_player_speed_team0 = np.mean(all_player_speeds_team0)
    else:
        average_player_speed_team0 = 0.0

    if all_player_speeds_team1:
        average_player_speed_team1 = np.mean(all_player_speeds_team1)
    else:
        average_player_speed_team1 = 0.0

    if all_ball_speeds:
        average_ball_speed = np.mean(all_ball_speeds)
    else:
        average_ball_speed = 0.0

    # ------------------------------------------------------------
    # Compute Total Distances
    # ------------------------------------------------------------
    # Total distances are already accumulated in total_distance_team0, total_distance_team1, total_distance_ball

    return (
        team_0_possession_frames,
        team_1_possession_frames,
        frame_data,
        average_player_speed_team0,
        average_player_speed_team1,
        average_ball_speed,
        total_distance_team0,
        total_distance_team1,
        total_distance_ball
    )


def process_video(video_path, output_path, model, key_point_model, device, team_colors, progress_callback=None):
    BALL_ID = 0
    GOALKEEPER_ID = 1
    PLAYER_ID = 2
    REFEREE_ID = 3

    POSSESSION_THRESHOLD = 50

    tracker = sv.ByteTrack()
    tracker.reset()

    # 2) This dictionary will hold the last few positions for each track_id
    #    key = track_id (int), value = deque of (x, y) positions
    speed_buffer = defaultdict(lambda: deque(maxlen=10))  # or maxlen=3 if you prefer
    ball_speed_buffer = defaultdict(lambda: deque(maxlen=30))
    # Annotators
    ellipse_annotator = sv.EllipseAnnotator(
        color=sv.ColorPalette.from_hex(['#00BFFF', '#FF1493', '#FFD700']),
        thickness=2
    )
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

    ball_annotator = sv.LabelAnnotator(
        color=sv.ColorPalette.from_hex(['#FFD700']),
        text_color=sv.Color.from_hex('#000000'),
        text_position=sv.Position.BOTTOM_CENTER
    )
    

    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = cv2.VideoWriter(os.path.join(output_path, "video_output.mp4"), cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))
    frames = []
    batch_size = 16

    # Variables for possession tracking
    team_0_possession_frames = 0
    team_1_possession_frames = 0
    team_1_speed = 0
    team_2_speed = 0
    ball_speed = 0
    team_1_distance = 0
    team_2_distance = 0
    ball_distance = 0
    counter = 0
    frame_counter = 0


    all_frame_data = []
    last_player_positions = np.array([])  # empty at the start

    print("Processing video and collecting frame data...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(frame_rgb)
        frame_counter += 1
        if progress_callback is not None:
            progress_callback(frame_counter, frame_total)

        if len(frames) == batch_size:
            (team_0_possession_frames,
             team_1_possession_frames,
             frame_data, avg_team1_speed, avg_team2_speed, avg_ball_speed, avg_distance_team1, avg_distance_team2, avg_distance_ball) = process_batch(
                 frames,
                 model,
                 key_point_model,
                 device,
                 team_colors,
                 POSSESSION_THRESHOLD,
                 BALL_ID,
                 GOALKEEPER_ID,
                 PLAYER_ID,
                 REFEREE_ID,
                 triangle_annotator,
                 ellipse_annotator,
                 label_annotator,
                 ball_annotator,
                 out,
                 team_0_possession_frames,
                 team_1_possession_frames,
                 last_player_positions,
                 fps,
                 # Pass your tracker and the speed_buffer
                 tracker=tracker,
                 speed_buffer=speed_buffer,
                 ball_speed_buffer=ball_speed_buffer
             )
            print(f"Average player speed: {avg_team1_speed:.2f}, Average ball speed: {avg_team2_speed}, ball speed {avg_ball_speed} km/h")
            team_1_speed += avg_team1_speed
            team_2_speed += avg_team2_speed
            ball_speed += avg_ball_speed
            team_1_distance += avg_distance_team1
            team_2_distance += avg_distance_team2
            ball_distance += avg_distance_ball
            counter += 1

            all_frame_data.extend(frame_data)
            frames = []

    if len(frames) > 0:
        (team_0_possession_frames,
             team_1_possession_frames,
             frame_data, avg_team1_speed, avg_team2_speed, avg_ball_speed, avg_distance_team1, avg_distance_team2, avg_distance_ball) = process_batch(
                 frames,
                 model,
                 key_point_model,
                 device,
                 team_colors,
                 POSSESSION_THRESHOLD,
                 BALL_ID,
                 GOALKEEPER_ID,
                 PLAYER_ID,
                 REFEREE_ID,
                 triangle_annotator,
                 ellipse_annotator,
                 label_annotator,
                 ball_annotator,
                 out,
                 team_0_possession_frames,
                 team_1_possession_frames,
                 last_player_positions,
                 fps,
                 # Pass your tracker and the speed_buffer
                 tracker=tracker,
                 speed_buffer=speed_buffer,
                 ball_speed_buffer=ball_speed_buffer
             )
        all_frame_data.extend(frame_data)
        team_1_speed += avg_team1_speed
        team_2_speed += avg_team2_speed
        ball_speed += avg_ball_speed
        team_1_distance += avg_distance_team1
        team_2_distance += avg_distance_team2
        ball_distance += avg_distance_ball
        counter += 1

    
    avg_speeds = [team_1_speed/counter, team_2_speed/counter , ball_speed/counter]
    avg_distances = [team_1_distance/counter, team_2_distance/counter, ball_distance/counter]

    cap.release()

    # Calculate ball possession percentages
    total_possession_frames = team_0_possession_frames + team_1_possession_frames
    if total_possession_frames > 0:
        team_0_possession_percent = (team_0_possession_frames / total_possession_frames) * 100
        team_1_possession_percent = (team_1_possession_frames / total_possession_frames) * 100
    else:
        team_0_possession_percent = 0
        team_1_possession_percent = 0

    return team_0_possession_percent, team_1_possession_percent, all_frame_data, avg_speeds, avg_distances, counter


def create_ball_path(ball_positions, output_path="ball_path.mp4"):
    print("Creating ball path on the pitch...")

    # Flatten list of ball positions
    flattened_positions = [
        {'frame': frame_idx, 'x': pos[0], 'y': pos[1]}
        for frame_idx, frame_positions in enumerate(ball_positions)
        for pos in frame_positions
    ]

    ball_positions_df = pd.DataFrame(flattened_positions)

    # Step 1: Removing outliers
    clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=20, linkage='single')
    positions = ball_positions_df[['x', 'y']].to_numpy()
    labels = clustering.fit_predict(positions)

    inlier_mask = labels != -1
    inlier_positions = ball_positions_df[inlier_mask]

    # Step 2: Smoothing ball path with Kalman filter
    smoothed_positions = []
    for _, row in inlier_positions.iterrows():
        x_smooth, y_smooth = ball_smoother.smooth(object_id='ball', current_position=(row['x'], row['y']))
        smoothed_positions.append({'frame': row['frame'], 'x': x_smooth, 'y': y_smooth})

    smoothed_df = pd.DataFrame(smoothed_positions)

    # Step 3: Identifying segments when the ball is moving on the ground
    ransac = RANSACRegressor(residual_threshold=50)  # Adjust threshold based on dataset
    ground_segments = []
    smoothed_array = smoothed_df[['x', 'y']].to_numpy()
    if len(smoothed_array) > 5:  # Ensure enough points for RANSAC
        try:
            ransac.fit(np.arange(len(smoothed_array)).reshape(-1, 1), smoothed_array)
            inlier_mask = ransac.inlier_mask_
            ground_segments = smoothed_df[inlier_mask]
        except ValueError:
            print("RANSAC failed due to insufficient or unsuitable data for ground segment fitting.")

    # Step 4: Finding points where the ball rebounds
    rebound_points = []
    velocities = np.diff(smoothed_array, axis=0)
    mean_velocity_change = np.mean(np.linalg.norm(velocities, axis=1))
    threshold = mean_velocity_change * 1.25  # Use a dynamic threshold

    for i in range(1, len(velocities)):
        velocity_change = np.linalg.norm(velocities[i] - velocities[i - 1])
        if velocity_change > threshold:
            rebound_points.append(smoothed_df.iloc[i])

    rebound_df = pd.DataFrame(rebound_points)
    rebound_df = rebound_df.sort_values('frame').reset_index(drop=True)  # Ensure sorted by frame

    # Step 5: Interpolating trajectory
    interpolated_positions = []
    for i in range(len(rebound_df) - 1):
        start = rebound_df.iloc[i]
        end = rebound_df.iloc[i + 1]
        num_points = int(end['frame'] - start['frame'])
        if num_points > 1:  # Avoid single-point segments
            x_interp = np.linspace(start['x'], end['x'], num_points)
            y_interp = np.linspace(start['y'], end['y'], num_points)
            for j in range(num_points):
                interpolated_positions.append({'frame': int(start['frame'] + j), 'x': x_interp[j], 'y': y_interp[j]})

    interpolated_df = pd.DataFrame(interpolated_positions).sort_values('frame').reset_index(drop=True)


    final_positions = []
    grouped = interpolated_df.groupby('frame')
    for frame_idx, group in grouped:
        frame_positions = group[['x', 'y']].to_numpy()
        final_positions.append(frame_positions)

    # Create output video
    print("Drawing ball path on the pitch...")
    annotated_frames = []

    annotated_frame = draw_pitch(CONFIG)
    for frame in final_positions:
        annotated_frame = draw_points_on_pitch(
            config=CONFIG,
            xy=frame,
            face_color=sv.Color.WHITE,
            edge_color=sv.Color.BLACK,
            radius=5,
            pitch=annotated_frame)
        annotated_frames.append(cv2.rotate(annotated_frame.copy(), cv2.ROTATE_90_CLOCKWISE))

    pitch_out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), 30, (annotated_frames[0].shape[1], annotated_frames[0].shape[0]))
    for frame in annotated_frames:
        pitch_out.write(frame)
    pitch_out.release()

    print(f"Ball path video created at {output_path}")


def calculate_players_speed(all_frame_data):
    pass

    

def create_pitch_video(all_frame_data, output_path):
    print("Generating pitch video...")
    annotated_frames = []
    ball_positions = []

    for frame_data in all_frame_data:
        kp_detections = frame_data['keypoints']
        ball_detections = frame_data['ball']
        players_detections = frame_data['players']
        referees_detections = frame_data['referees']

        filter = kp_detections.confidence[0] > 0.8
        frame_reference_points = kp_detections.xy[0][filter]
        pitch_reference_points = np.array(CONFIG.vertices)[filter]

        transformer = ViewTransformer(frame_reference_points, pitch_reference_points)
        pitch_ball_xy = transformer.transform_points(points=ball_detections)
        ball_positions.append(pitch_ball_xy)

        players_xy = players_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_players_xy = transformer.transform_points(points=players_xy)

        referees_xy = referees_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_referees_xy = transformer.transform_points(points=referees_xy)

        annotated_frame = draw_pitch(CONFIG)

        annotated_frame = draw_points_on_pitch(
            config=CONFIG,
            xy=pitch_ball_xy,
            face_color=sv.Color.WHITE,
            edge_color=sv.Color.BLACK,
            radius=10,
            pitch=annotated_frame)
        annotated_frame = draw_points_on_pitch(
            config=CONFIG,
            xy=pitch_players_xy[players_detections.class_id == 0],
            face_color=sv.Color.from_hex('00BFFF'),
            edge_color=sv.Color.BLACK,
            radius=16,
            pitch=annotated_frame)
        annotated_frame = draw_points_on_pitch(
            config=CONFIG,
            xy=pitch_players_xy[players_detections.class_id == 1],
            face_color=sv.Color.from_hex('FF1493'),
            edge_color=sv.Color.BLACK,
            radius=16,
            pitch=annotated_frame)
        annotated_frame = draw_points_on_pitch(
            config=CONFIG,
            xy=pitch_referees_xy,
            face_color=sv.Color.from_hex('FFD700'),
            edge_color=sv.Color.BLACK,
            radius=16,
            pitch=annotated_frame)

        annotated_frames.append(cv2.rotate(annotated_frame, cv2.ROTATE_90_CLOCKWISE))

    create_ball_path(ball_positions, os.path.join(output_path,"ball_path.mp4"))

    pitch_out = cv2.VideoWriter(os.path.join(output_path,"top_down_view.mp4"), cv2.VideoWriter_fourcc(*'mp4v'), 30, (annotated_frames[0].shape[1], annotated_frames[0].shape[0]))
    for frame in annotated_frames:
        pitch_out.write(frame)
    pitch_out.release()

def analyze_video_model(video_path, output_path, model_path="models/player_detection2.pt", progress_callback=None):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = load_model(model_path, device)
    key_point_model = load_model("models/key_point_detection.pt", device)

    team_colors = extract_team_colors(video_path, model, device)
    team1_possesion, team2_possesion, all_frame_data, avg_speeds, avg_distances, counter = process_video(video_path, output_path, model, key_point_model, device, team_colors, progress_callback)

    create_pitch_video(all_frame_data, output_path) 
    print("Pitch video with ball path created at pitch_with_path.mp4")

    return team1_possesion, team2_possesion, avg_speeds, avg_distances, counter
    

