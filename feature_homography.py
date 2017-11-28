import numpy as np
import cv2
import video
import common
from common import getsize, draw_keypoints
from plane_tracker import PlaneTracker


class App:
    def __init__(self, src):
        self.cap = video.create_capture(src)
        self.frame = None
        self.paused = False
        self.tracker = PlaneTracker()

        cv2.namedWindow('plane')
        self.rect_sel = common.RectSelector('plane', self.on_rect)

    def on_rect(self, rect):
        self.tracker.clear()
        self.tracker.add_target(self.frame, rect)

    def run(self):
        img = cv2.imread('image.jpg')
        while True:
            playing = not self.paused and not self.rect_sel.dragging
            if playing or self.frame is None:
                ret, frame = self.cap.read()
                if not ret:
                    break
                self.frame = frame.copy()

            w, h = getsize(self.frame)            
            vis = np.zeros((h, w*2, 3), np.uint8)
            vis[:h,:w] = self.frame
                        
            if len(self.tracker.targets) > 0:
                target = self.tracker.targets[0]
                vis[:,w:] = target.image            
                draw_keypoints(vis[:,w:], target.keypoints)
                x0, y0, x1, y1 = target.rect
                cv2.rectangle(vis, (x0+w, y0), (x1+w, y1), (0, 255, 0), 2)

            if playing:
                tracked = self.tracker.track(self.frame)
                if len(tracked) > 0:
                    tracked = tracked[0]
                    #cv2.fillPoly(vis, [np.int32(tracked.quad)], 255)
                    cv2.polylines(vis, [np.int32(tracked.quad)], True, (255, 0, 0), 2)
                    
                    xt,yt=tracked.quad[3]
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(vis,'Planar track',(xt,yt), font, 1,(0,0,255),2)
                    cv2.circle(vis,(xt,yt), 30, (0,255,0), 2)
                                        
                    #for (x0, y0), (x1, y1) in zip(np.int32(tracked.p0), np.int32(tracked.p1)):
                    #    cv2.line(vis, (x0+w, y0), (x1, y1), (0, 255, 0))                        
            draw_keypoints(vis, self.tracker.frame_points)
            
            
            
            self.rect_sel.draw(vis)
            cv2.imshow('plane', vis)
            ch = cv2.waitKey(1)
            if ch == ord(' '):
                self.paused = not self.paused
            if ch == 27:
                break


if __name__ == '__main__':
    print __doc__

    import sys
    try: video_src = sys.argv[1]
    except: video_src = 0
    App(video_src).run()
