import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import cv2
import torch


from video_analysis import (
    extract_average_color,
    classify_player,
    get_center,
    resolve_goalkeepers_team_id,
    load_model,
    extract_team_colors,
    process_batch,
    process_video,
    main
)

import supervision as sv

class TestHelperFunctions(unittest.TestCase):
    def test_extract_average_color(self):
        blue = np.zeros((64, 64, 3), dtype=np.uint8)
        blue[:] = [255, 0, 0] 
        avg_color = extract_average_color(blue)
        self.assertEqual(avg_color.shape, (3,))
        self.assertTrue(100 <= avg_color[0] <= 140) 

    def test_classify_player(self):
        # Suppose we have two team colors: 
        # Team 0: mean_color ~ [100, 150, 200]
        # Team 1: mean_color ~ [50,  100, 50]
        team_colors = np.array([
            [100, 150, 200],
            [50, 100, 50]
        ])
        dominant_color = np.array([90, 140, 190])  # Closer to team 0
        team_id = classify_player(dominant_color, team_colors)
        self.assertEqual(team_id, 0)

    def test_get_center(self):
        box = [10, 20, 30, 40]  
        center = get_center(box)
        np.testing.assert_array_equal(center, np.array([20,30]))

    def test_resolve_goalkeepers_team_id(self):
        players = MagicMock(spec=sv.Detections)
        goalkeepers = MagicMock(spec=sv.Detections)

        players.__len__.return_value = 4
        goalkeepers.__len__.return_value = 2

        players.get_anchors_coordinates.return_value = np.array([
            [100, 100],
            [110, 110],
            [200, 200],
            [210, 210]
        ])
        players.class_id = np.array([0,0,1,1])

        goalkeepers.get_anchors_coordinates.return_value = np.array([
            [105,105],
            [205,205]
        ])

        result = resolve_goalkeepers_team_id(players, goalkeepers)
        np.testing.assert_array_equal(result, np.array([0,1]))


class TestModelFunctions(unittest.TestCase):
    @patch('video_analysis.YOLO', autospec=True)
    def test_load_model(self, mock_yolo):
        device = torch.device('cpu')
        model_path = 'models/player_detection.pt'
        model = load_model(model_path, device)
        mock_yolo.assert_called_with(model_path)
        mock_yolo.return_value.to.assert_called_with(device)
        self.assertEqual(model, mock_yolo.return_value)

    @patch('video_analysis.cv2.VideoCapture', autospec=True)
    @patch('video_analysis.YOLO')
    @patch('video_analysis.extract_average_color', return_value=np.array([100,150,200]))
    def test_extract_team_colors(self, mock_extract_color, mock_yolo, mock_capture):
        # Mock VideoCapture behavior
        cap_instance = mock_capture.return_value
        cap_instance.get.side_effect = lambda x: 3 if x == cv2.CAP_PROP_FRAME_COUNT else 0
        cap_instance.read.side_effect = [
            (True, np.zeros((720,1280,3), dtype=np.uint8)),
            (False, None)
        ]

        
        mock_boxes = MagicMock()
        # Now we return two detections for players:
        mock_boxes.xyxy.cpu().numpy.return_value = np.array([
            [100,100,200,200],
            [300,300,400,400]
        ])
        mock_boxes.conf.cpu().numpy.return_value = np.array([0.9, 0.95])
        mock_boxes.cls.cpu().numpy.return_value = np.array([2, 2])  

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        model = MagicMock()
        model.return_value = [mock_result]  

        device = torch.device('cuda')

        team_colors = extract_team_colors('test.mp4', model, device, stride=30, max_frames=10)
        self.assertEqual(team_colors.shape, (2,3))

    @patch('video_analysis.process_batch')
    @patch('video_analysis.cv2.VideoCapture', autospec=True)
    @patch('video_analysis.cv2.VideoWriter', autospec=True)
    def test_process_video(self, mock_writer, mock_capture, mock_process_batch):
        # Mock video capture
        cap_instance = mock_capture.return_value
        cap_instance.read.side_effect = [
            (True, np.zeros((720,1280,3), dtype=np.uint8)),  # One frame
            (False, None)
        ]
        cap_instance.get.side_effect = lambda x: 1 if x == cv2.CAP_PROP_FRAME_COUNT else 30 if x == cv2.CAP_PROP_FPS else 1280 if x == cv2.CAP_PROP_FRAME_WIDTH else 720 if x == cv2.CAP_PROP_FRAME_HEIGHT else 0
        
        # Mock writer
        writer_instance = mock_writer.return_value

        model = MagicMock()
        device = torch.device('cuda')
        team_colors = np.array([[100,150,200],[50,100,50]])

        # Mock process_batch return values
        mock_process_batch.return_value = (5, 3)

        t0_pct, t1_pct = process_video('test.mp4', 'output.mp4', model, device, team_colors)
        self.assertAlmostEqual(t0_pct, 62.5)
        self.assertAlmostEqual(t1_pct, 37.5)


class TestIntegration(unittest.TestCase):
    @patch('video_analysis.process_video', return_value=(60.0,40.0))
    @patch('video_analysis.extract_team_colors', return_value=np.array([[100,150,200],[50,100,50]]))
    @patch('video_analysis.load_model', return_value=MagicMock())
    def test_main(self, mock_load_model, mock_extract_team_colors, mock_process_video):
        main('test.mp4', 'ball_possession.mp4', model_path="models/player_detection.pt")
        mock_load_model.assert_called_once()
        mock_extract_team_colors.assert_called_once()
        mock_process_video.assert_called_once()


if __name__ == '__main__':
    unittest.main()
