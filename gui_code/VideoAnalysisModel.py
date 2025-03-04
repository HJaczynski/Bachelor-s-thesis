import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
import torch
from tqdm import tqdm
from sklearn.cluster import KMeans, AgglomerativeClustering
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
    """
    Smooths the positions of detected objects to reduce jitter in tracking.

    Attributes:
        alpha (float): Smoothing factor between 0 and 1.
        last_positions (dict): Stores the last known positions of objects.
    """

    def __init__(self, alpha=0.3):
        """
        Initializes the PositionSmoother with a specified smoothing factor.

        Args:
            alpha (float, optional): Smoothing factor. Defaults to 0.3.
        """
        self.alpha = alpha
        self.last_positions = {}

    def smooth(self, object_id, current_position):
        """
        Applies exponential smoothing to the current position of an object.

        Args:
            object_id (hashable): Unique identifier for the object.
            current_position (tuple): Current (x, y) position of the object.

        Returns:
            tuple: Smoothed (x, y) position.
        """
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
    """
    Extracts the average HSV color from a given image.

    Args:
        image (numpy.ndarray): Input image in BGR format.

    Returns:
        numpy.ndarray: Average HSV color as a 1D array.
    """
    image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    image = cv2.resize(image, (32, 32))
    mean_color = image.mean(axis=(0, 1))
    return mean_color


def classify_player(dominant_color, team_colors):
    """
    Classifies a player into a team based on the closest team color.

    Args:
        dominant_color (numpy.ndarray): Dominant HSV color of the player.
        team_colors (numpy.ndarray): Array of team HSV colors.

    Returns:
        int: Team ID (index of the closest team color).
    """
    distances = np.linalg.norm(team_colors - dominant_color, axis=1)
    team_id = np.argmin(distances)
    return team_id


def get_center(box):
    """
    Calculates the center coordinates of a bounding box.

    Args:
        box (iterable): Bounding box coordinates [x1, y1, x2, y2].

    Returns:
        numpy.ndarray: Center (x, y) coordinates.
    """
    x_center = (box[0] + box[2]) / 2
    y_center = (box[1] + box[3]) / 2
    return np.array([x_center, y_center])


def resolve_goalkeepers_team_id(players, goalkeepers):
    """
    Assigns team IDs to goalkeepers based on their distance to team centroids.

    Args:
        players (sv.Detections): Detected players with team IDs.
        goalkeepers (sv.Detections): Detected goalkeepers.

    Returns:
        numpy.ndarray: Array of team IDs for each goalkeeper.
    """
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
    """
    Loads a YOLO model from the specified path and moves it to the given device.

    Args:
        model_path (str): Path to the YOLO model file.
        device (torch.device): Device to load the model onto.

    Returns:
        YOLO: Loaded YOLO model.
    """
    model = YOLO(model_path)
    model.to(device)
    return model


def run_yolo_model(frames, model, device):
    """
    Runs the YOLO model on a batch of frames.

    Args:
        frames (list of numpy.ndarray): List of frames to process.
        model (YOLO): YOLO model for detection.
        device (torch.device): Device to perform computation on.

    Returns:
        list: Detection results for each frame.
    """
    return model(frames, device=device)


def run_keypoint_model(frames, key_point_model, device):
    """
    Runs the keypoint detection model on a batch of frames.

    Args:
        frames (list of numpy.ndarray): List of frames to process.
        key_point_model (YOLO): Keypoint detection model.
        device (torch.device): Device to perform computation on.

    Returns:
        list: Keypoint detection results for each frame.
    """
    return key_point_model(frames, device=device)


def run_simultaneous_inference(frames, yolo_model, key_point_model, device):
    """
    Runs YOLO and keypoint models concurrently on a batch of frames.

    Args:
        frames (list of numpy.ndarray): List of frames to process.
        yolo_model (YOLO): YOLO model for object detection.
        key_point_model (YOLO): Keypoint detection model.
        device (torch.device): Device to perform computation on.

    Returns:
        tuple: (YOLO results, Keypoint detection results)
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_yolo = executor.submit(run_yolo_model, frames, yolo_model, device)
        future_keypoints = executor.submit(run_keypoint_model, frames, key_point_model, device)

        results_yolo = future_yolo.result()
        results_keypoints = future_keypoints.result()

    return results_yolo, results_keypoints


def extract_team_colors(video_path, model, device, stride=30, max_frames=10):
    """
    Extracts the dominant team colors by analyzing initial frames of the video.

    Args:
        video_path (str): Path to the input video file.
        model (YOLO): YOLO model for player detection.
        device (torch.device): Device to perform computation on.
        stride (int, optional): Frame interval for sampling. Defaults to 30.
        max_frames (int, optional): Maximum number of frames to analyze. Defaults to 10.

    Returns:
        numpy.ndarray: Array containing the HSV colors of the two teams.
    """
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
    last_player_positions=None,
    fps=30,
    tracker=None,
    speed_buffer=None,
    ball_speed_buffer=None,
    homography_conf_threshold=0.8
):
    """
    Processes a batch of frames to perform detection, tracking, possession analysis, and annotation.

    Args:
        frames (list of numpy.ndarray): List of frames to process.
        model (YOLO): YOLO model for object detection.
        key_point_model (YOLO): Keypoint detection model.
        device (torch.device): Device to perform computation on.
        team_colors (numpy.ndarray): Array of team HSV colors.
        POSSESSION_THRESHOLD (float): Distance threshold to determine ball possession.
        BALL_ID (int): Class ID for the ball.
        GOALKEEPER_ID (int): Class ID for goalkeepers.
        PLAYER_ID (int): Class ID for players.
        REFEREE_ID (int): Class ID for referees.
        triangle_annotator (sv.TriangleAnnotator, optional): Annotator for triangles. Defaults to None.
        ellipse_annotator (sv.EllipseAnnotator, optional): Annotator for ellipses. Defaults to None.
        label_annotator (sv.LabelAnnotator, optional): Annotator for labels. Defaults to None.
        ball_annotator (sv.LabelAnnotator, optional): Annotator for the ball. Defaults to None.
        out (cv2.VideoWriter, optional): Video writer for output. Defaults to None.
        team_0_possession_frames (int, optional): Initial possession frames for team 0. Defaults to 0.
        team_1_possession_frames (int, optional): Initial possession frames for team 1. Defaults to 0.
        last_player_positions (list, optional): Last known positions of players. Defaults to None.
        fps (int, optional): Frames per second of the video. Defaults to 30.
        tracker (sv.ByteTrack, optional): Object tracker. Defaults to None.
        speed_buffer (defaultdict, optional): Buffer for tracking speeds. Defaults to None.
        ball_speed_buffer (defaultdict, optional): Buffer for ball speed tracking. Defaults to None.
        homography_conf_threshold (float, optional): Confidence threshold for homography. Defaults to 0.8.

    Returns:
        tuple: Contains updated possession frames, frame data, average speeds, and total distances.
    """
    if last_player_positions is None:
        last_player_positions = []

    if tracker is None:
        tracker = sv.ByteTrack()
        tracker.reset()

    if speed_buffer is None:
        speed_buffer = defaultdict(lambda: deque(maxlen=2))

    if ball_speed_buffer is None:
        ball_speed_buffer = defaultdict(lambda: deque(maxlen=2))

    all_player_speeds_team0 = []
    all_player_speeds_team1 = []
    all_ball_speeds = []

    total_distance_team0 = 0.0
    total_distance_team1 = 0.0
    total_distance_ball = 0.0

    results, results_keypoints = run_simultaneous_inference(frames, model, key_point_model, device)

    frame_data = []

    for i, (result, result_kpts) in enumerate(zip(results, results_keypoints)):

        detections = sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int)
        )

        kp_detections = sv.KeyPoints.from_ultralytics(result_kpts)

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

        ball_detections = detections[detections.class_id == BALL_ID]
        ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

        all_detections = detections[detections.class_id != BALL_ID]
        all_detections = all_detections.with_nms(threshold=0.5, class_agnostic=True)

        goalkeepers_detections = all_detections[all_detections.class_id == GOALKEEPER_ID]
        players_detections = all_detections[all_detections.class_id == PLAYER_ID]
        referees_detections = all_detections[all_detections.class_id == REFEREE_ID]

        team_ids = []
        for xyxy in players_detections.xyxy:
            crop = sv.crop_image(frames[i], xyxy)
            dominant_color = extract_average_color(crop)
            team_id = classify_player(dominant_color, team_colors)
            team_ids.append(team_id)
        players_detections.class_id = np.array(team_ids)

        goalkeepers_detections.class_id = resolve_goalkeepers_team_id(players_detections, goalkeepers_detections)

        all_detections = sv.Detections.merge([players_detections, goalkeepers_detections, referees_detections])

        all_detections = tracker.update_with_detections(detections=all_detections)

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

        speed_detections = all_detections[np.isin(all_detections.class_id, [0, 1])]
        current_positions_px = speed_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)

        current_positions_m = transformer.transform_points(current_positions_px)

        speeds_kmh = []
        for track_id, (mx, my), team_id in zip(speed_detections.tracker_id, current_positions_m, speed_detections.class_id):
            if track_id == -1:
                speed_kmh = 0.0
                speeds_kmh.append(speed_kmh)
                continue

            if len(speed_buffer[track_id]) >= 1:
                prev_mx, prev_my = speed_buffer[track_id][-1]
                distance_m = np.hypot(mx - prev_mx, my - prev_my)
                if team_id == 0:
                    total_distance_team0 += distance_m
                elif team_id == 1:
                    total_distance_team1 += distance_m

            speed_buffer[track_id].append((mx, my))

            if len(speed_buffer[track_id]) >= 2:
                (mx_old, my_old) = speed_buffer[track_id][0]
                (mx_new, my_new) = speed_buffer[track_id][-1]
                dist_m = np.hypot(mx_new - mx_old, my_new - my_old)

                frame_intervals = len(speed_buffer[track_id]) - 1

                speed_m_s = dist_m * (fps / frame_intervals)
                speed_kmh = speed_m_s * 3.6
            else:
                speed_kmh = 0.0

            speeds_kmh.append(speed_kmh)

            if team_id == 0:
                all_player_speeds_team0.append(speed_kmh)
            elif team_id == 1:
                all_player_speeds_team1.append(speed_kmh)

        labels = [f"{s:.1f} km/h" for s in speeds_kmh]

        frame_bgr = cv2.cvtColor(frames[i], cv2.COLOR_RGB2BGR)

        if len(ball_detections) > 0:
            sorted_indices = np.argsort(-ball_detections.confidence)
            best_index = sorted_indices[0]
            best_ball = ball_detections[best_index:best_index+1]

            ball_detections_speed = best_ball.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            ball_positions_m = transformer.transform_points(ball_detections_speed)

            if len(ball_positions_m) > 0:
                if len(ball_speed_buffer[0]) >= 1:
                    prev_ball_mx, prev_ball_my = ball_speed_buffer[0][-1]
                    ball_distance_m = np.hypot(ball_positions_m[0][0] - prev_ball_mx, ball_positions_m[0][1] - prev_ball_my)
                    total_distance_ball += ball_distance_m

                ball_speed_buffer[0].append(ball_positions_m[0])

                if len(ball_speed_buffer[0]) >= 2:
                    (mx_old, my_old) = ball_speed_buffer[0][0]
                    (mx_new, my_new) = ball_speed_buffer[0][-1]
                    dist_m = np.hypot(mx_new - mx_old, my_new - my_old)
                    frame_intervals = len(ball_speed_buffer[0]) - 1
                    speed_m_s = dist_m * (fps / frame_intervals)
                    speed_kmh = speed_m_s * 3.6
                else:
                    speed_kmh = 0.0

                all_ball_speeds.append(speed_kmh)

                ball_label = [f"Ball: {speed_kmh:.1f} km/h"]

                annotated_frame = ball_annotator.annotate(
                    scene=frame_bgr,
                    detections=best_ball,
                    labels=ball_label
                )
            else:
                annotated_frame = frame_bgr
        else:
            annotated_frame = frame_bgr

        annotated_frame = ellipse_annotator.annotate(scene=annotated_frame, detections=all_detections)
        annotated_frame = triangle_annotator.annotate(scene=annotated_frame, detections=ball_detections)

        if label_annotator is not None:
            annotated_frame = label_annotator.annotate(
                scene=annotated_frame,
                detections=speed_detections,
                labels=labels
            )

        out.write(annotated_frame)

        frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_data = {
            'keypoints': kp_detections,
            'ball': frame_ball_xy,
            'players': players_detections,
            'referees': referees_detections
        }
        frame_data.append(pitch_data)

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
    """
    Processes the entire video to perform detection, tracking, analysis, and annotation.

    Args:
        video_path (str): Path to the input video file.
        output_path (str): Directory to save the annotated output video.
        model (YOLO): YOLO model for object detection.
        key_point_model (YOLO): Keypoint detection model.
        device (torch.device): Device to perform computation on.
        team_colors (numpy.ndarray): Array of team HSV colors.
        progress_callback (callable, optional): Function to update progress. Defaults to None.

    Returns:
        tuple: Contains possession percentages, frame data, average speeds, distances, and frame count.
    """
    BALL_ID = 0
    GOALKEEPER_ID = 1
    PLAYER_ID = 2
    REFEREE_ID = 3

    POSSESSION_THRESHOLD = 50

    tracker = sv.ByteTrack()
    tracker.reset()

    speed_buffer = defaultdict(lambda: deque(maxlen=10))
    ball_speed_buffer = defaultdict(lambda: deque(maxlen=30))
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
    last_player_positions = np.array([])

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

    avg_speeds = [team_1_speed/counter, team_2_speed/counter, ball_speed/counter]
    avg_distances = [team_1_distance/counter, team_2_distance/counter, ball_distance/counter]

    cap.release()

    total_possession_frames = team_0_possession_frames + team_1_possession_frames
    if total_possession_frames > 0:
        team_0_possession_percent = (team_0_possession_frames / total_possession_frames) * 100
        team_1_possession_percent = (team_1_possession_frames / total_possession_frames) * 100
    else:
        team_0_possession_percent = 0
        team_1_possession_percent = 0

    return team_0_possession_percent, team_1_possession_percent, all_frame_data, avg_speeds, avg_distances, counter


def create_ball_path(ball_positions, output_path="ball_path.mp4"):
    """
    Creates a video showing the ball's path on the soccer pitch.

    Args:
        ball_positions (list of numpy.ndarray): List of ball positions per frame.
        output_path (str, optional): Path to save the ball path video. Defaults to "ball_path.mp4".
    """
    print("Creating ball path on the pitch...")

    flattened_positions = [
        {'frame': frame_idx, 'x': pos[0], 'y': pos[1]}
        for frame_idx, frame_positions in enumerate(ball_positions)
        for pos in frame_positions
    ]

    ball_positions_df = pd.DataFrame(flattened_positions)

    clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=20, linkage='single')
    positions = ball_positions_df[['x', 'y']].to_numpy()
    labels = clustering.fit_predict(positions)

    inlier_mask = labels != -1
    inlier_positions = ball_positions_df[inlier_mask]

    smoothed_positions = []
    for _, row in inlier_positions.iterrows():
        x_smooth, y_smooth = ball_smoother.smooth(object_id='ball', current_position=(row['x'], row['y']))
        smoothed_positions.append({'frame': row['frame'], 'x': x_smooth, 'y': y_smooth})

    smoothed_df = pd.DataFrame(smoothed_positions)

    ransac = RANSACRegressor(residual_threshold=50)
    ground_segments = []
    smoothed_array = smoothed_df[['x', 'y']].to_numpy()
    if len(smoothed_array) > 5:
        try:
            ransac.fit(np.arange(len(smoothed_array)).reshape(-1, 1), smoothed_array)
            inlier_mask = ransac.inlier_mask_
            ground_segments = smoothed_df[inlier_mask]
        except ValueError:
            print("RANSAC failed due to insufficient or unsuitable data for ground segment fitting.")

    rebound_points = []
    velocities = np.diff(smoothed_array, axis=0)
    mean_velocity_change = np.mean(np.linalg.norm(velocities, axis=1))
    threshold = mean_velocity_change * 1.25

    for i in range(1, len(velocities)):
        velocity_change = np.linalg.norm(velocities[i] - velocities[i - 1])
        if velocity_change > threshold:
            rebound_points.append(smoothed_df.iloc[i])

    rebound_df = pd.DataFrame(rebound_points)
    rebound_df = rebound_df.sort_values('frame').reset_index(drop=True)

    interpolated_positions = []
    for i in range(len(rebound_df) - 1):
        start = rebound_df.iloc[i]
        end = rebound_df.iloc[i + 1]
        num_points = int(end['frame'] - start['frame'])
        if num_points > 1:
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


def create_pitch_video(all_frame_data, output_path):
    """
    Generates a top-down view video of the pitch with annotated player and ball positions.

    Args:
        all_frame_data (list of dict): List containing detection data for each frame.
        output_path (str): Directory to save the generated pitch video and ball path.
    """
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

    create_ball_path(ball_positions, os.path.join(output_path, "ball_path.mp4"))

    pitch_out = cv2.VideoWriter(os.path.join(output_path, "top_down_view.mp4"), cv2.VideoWriter_fourcc(*'mp4v'), 30, (annotated_frames[0].shape[1], annotated_frames[0].shape[0]))
    for frame in annotated_frames:
        pitch_out.write(frame)
    pitch_out.release()


def analyze_video_model(video_path, output_path, model_path="models/player_detection2.pt", progress_callback=None):
    """
    Analyzes a soccer video to detect players, track movements, determine possession, and generate annotated outputs.

    Args:
        video_path (str): Path to the input video file.
        output_path (str): Directory to save the annotated output videos.
        model_path (str, optional): Path to the player detection model. Defaults to "models/player_detection2.pt".
        progress_callback (callable, optional): Function to update progress. Defaults to None.

    Returns:
        tuple: Contains possession percentages, average speeds, distances, and frame count.
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = load_model(model_path, device)
    key_point_model = load_model("models/key_point_detection.pt", device)

    team_colors = extract_team_colors(video_path, model, device)
    team1_possesion, team2_possesion, all_frame_data, avg_speeds, avg_distances, counter = process_video(video_path, output_path, model, key_point_model, device, team_colors, progress_callback)

    create_pitch_video(all_frame_data, output_path)
    print("Pitch video with ball path created at pitch_with_path.mp4")

    return team1_possesion, team2_possesion, avg_speeds, avg_distances, counter
