import supervision as sv

class Annotations:
    def __init__(self, video_path, frame, detections):
        tracker = sv.ByteTrack()
        tracker.reset()

        
        ball_detections = detections[detections.class_id == 0]
        ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

        
        all_detections = detections[detections.class_id != 0]
        all_detections = all_detections.with_nms(threshold=0.5, class_agnostic=True)
        all_detections.class_id -= 1

        
        labels = [
            f"#{tracker_id}" for tracker_id in all_detections.tracker_id
        ]

        self.labels = labels
        self.video_path = video_path
        self.frame = frame
        self.ball_detections = ball_detections
        self.all_detections = tracker.update_with_detections(detections=all_detections)

    def ellipse_annotation(self):
        ellipse_annotator = sv.EllipseAnnotator(
            color=sv.ColorPallette.from_hex(['#FF0000', '#00FF00', '#0000FF']),
            thickness=2,
        )
        self.frame = ellipse_annotator.annotate(
            scene=self.frame,
            detections=self.all_detections
        )

    def triangle_annotation(self):
        triangle_annotator = sv.TriangleAnnotator(
            color=sv.ColorPallette.from_hex("#FFE4B5"),
            thickness=2,
        )
        self.frame = triangle_annotator.annotate(
            scene=self.frame,
            detections=self.ball_detections
        )

    def label_annotation(self):
        label_annotator = sv.LabelAnnotator(
            color=sv.ColorPallette.from_hex(['#FF0000', '#00FF00', '#0000FF']),
            text_color=sv.ColorPallette.from_hex('#000000'),
            text_position=sv.Position.BOTTOM,
        )
        self.frame = label_annotator.annotate(
            scene=self.frame,
            detections=self.all_detections,
            labels=self.labels
        )
        return self.frame  
    
    def annotate(self):
        self.ellipse_annotation()
        self.triangle_annotation()
        return self.label_annotation()  
