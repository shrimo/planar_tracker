import numpy as np
import cv2
from collections import namedtuple
import video
import common
from PyQt4 import QtGui, QtCore

FLANN_INDEX_KDTREE = 1
FLANN_INDEX_LSH    = 6
flann_params= dict(algorithm = FLANN_INDEX_LSH,
                   table_number = 6, # 12
                   key_size = 12,     # 20
                   multi_probe_level = 1) #2

MIN_MATCH_COUNT = 10

video_file = ''
image_file = ''
mask_file = ''
off_info = ''

'''
  image     - image to track
  rect      - tracked rectangle (x1, y1, x2, y2)
  keypoints - keypoints detected inside rect
  descrs    - their descriptors
  data      - some user-provided data
'''
PlanarTarget = namedtuple('PlaneTarget', 'image, rect, keypoints, descrs, data')

'''
  target - reference to PlanarTarget
  p0     - matched points coords in target image
  p1     - matched points coords in input frame
  H      - homography matrix from p0 to p1
  quad   - target bounary quad in input frame
'''
TrackedTarget = namedtuple('TrackedTarget', 'target, p0, p1, H, quad')

class PlaneTracker:
    def __init__(self):
        self.detector = cv2.ORB( nfeatures = 3000 )
        self.matcher = cv2.FlannBasedMatcher(flann_params, {})  # bug : need to pass empty dict (#1329)
        self.targets = []

    def add_target(self, image, rect, data=None):
        '''Add a new tracking target.'''
        x0, y0, x1, y1 = rect
        raw_points, raw_descrs = self.detect_features(image)
        points, descs = [], []
        for kp, desc in zip(raw_points, raw_descrs):
            x, y = kp.pt
            if x0 <= x <= x1 and y0 <= y <= y1:
                points.append(kp)
                descs.append(desc)
        descs = np.uint8(descs)
        self.matcher.add([descs])
        target = PlanarTarget(image = image, rect=rect, keypoints = points, descrs=descs, data=None)
        self.targets.append(target)

    def clear(self):
        '''Remove all targets'''
        self.targets = []
        self.matcher.clear()

    def track(self, frame):
        '''Returns a list of detected TrackedTarget objects'''
        self.frame_points, self.frame_descrs = self.detect_features(frame)
        if len(self.frame_points) < MIN_MATCH_COUNT:
            return []
        matches = self.matcher.knnMatch(self.frame_descrs, k = 2)
        matches = [m[0] for m in matches if len(m) == 2 and m[0].distance < m[1].distance * 0.75]
        if len(matches) < MIN_MATCH_COUNT:
            return []
        matches_by_id = [[] for _ in xrange(len(self.targets))]
        for m in matches:
            matches_by_id[m.imgIdx].append(m)
        tracked = []
        for imgIdx, matches in enumerate(matches_by_id):
            if len(matches) < MIN_MATCH_COUNT:
                continue
            target = self.targets[imgIdx]
            p0 = [target.keypoints[m.trainIdx].pt for m in matches]
            p1 = [self.frame_points[m.queryIdx].pt for m in matches]
            p0, p1 = np.float32((p0, p1))
            H, status = cv2.findHomography(p0, p1, cv2.RANSAC, 3.0)
            status = status.ravel() != 0
            if status.sum() < MIN_MATCH_COUNT:
                continue
            p0, p1 = p0[status], p1[status]

            x0, y0, x1, y1 = target.rect
            quad = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
            quad = cv2.perspectiveTransform(quad.reshape(1, -1, 2), H).reshape(-1, 2)

            track = TrackedTarget(target=target, p0=p0, p1=p1, H=H, quad=quad)
            tracked.append(track)
        tracked.sort(key = lambda t: len(t.p0), reverse=True)
        return tracked

    def detect_features(self, frame):
        '''detect_features(self, frame) -> keypoints, descrs'''
        keypoints, descrs = self.detector.detectAndCompute(frame, None)
        if descrs is None:  # detectAndCompute returns descs=None if not keypoints found
            descrs = []
        return keypoints, descrs


class App:
    def __init__(self, src,f_img,f_img2,off_info):
        self.cap = video.create_capture(src)
        self.f_img=f_img
        self.f_img2=f_img2
        self.off_info = off_info
        self.frame = None
        self.paused = True
        self.tracker = PlaneTracker()

        cv2.namedWindow('plane')
        self.rect_sel = common.RectSelector('plane', self.on_rect)

    def on_rect(self, rect):
        self.tracker.add_target(self.frame, rect)

    def run(self):
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        frame_width = self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
        frame_height = self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)
        
        img = cv2.imread(str(self.f_img))
        img = cv2.resize(img, (int(frame_width), int(frame_height)))

        img2 = cv2.imread(str(self.f_img2))
        img2 = cv2.resize(img2, (int(frame_width), int(frame_height)))

        rows,cols,channels = img2.shape
        roi = img[0:rows, 0:cols ]

        img2gray = cv2.cvtColor(img2,cv2.COLOR_BGR2GRAY)
        ret, mask = cv2.threshold(img2gray, 10, 255, cv2.THRESH_BINARY)
        img_fg = cv2.bitwise_and(img,img,mask = mask)

        pts1 = np.float32([[0,0],[0,frame_height],[frame_width,frame_height],[frame_width,0]])

        def export_nuke (xt1,yt1,xt2,yt2,xt3,yt3,xt4,yt4):
            ft1 = open("track_01.txt", "a")
            fw1=str(xt1)+' '+str(frame_height-yt1)+'\n'
            ft1.write(fw1)                    
            ft1.close
            ft2 = open("track_02.txt", "a")
            fw2=str(xt2)+' '+str(frame_height-yt2)+'\n'
            ft2.write(fw2)                    
            ft2.close
            ft3 = open("track_03.txt", "a")
            fw3=str(xt3)+' '+str(frame_height-yt3)+'\n'
            ft3.write(fw3)                    
            ft3.close
            ft4 = open("track_04.txt", "a")
            fw4=str(xt4)+' '+str(frame_height-yt4)+'\n'
            ft4.write(fw4)                    
            ft4.close
        
        while True:
            playing = not self.paused and not self.rect_sel.dragging
            if playing or self.frame is None:
                ret, frame = self.cap.read()
                if not ret:
                    break
                self.frame = frame.copy()

            vis = self.frame.copy()                     
               
            if playing:
                tracked = self.tracker.track(self.frame)
                for tr in tracked:
                   
                    xt1,yt1 = tr.quad[0]
                    xt2,yt2 = tr.quad[3]
                    xt3,yt3 = tr.quad[2]
                    xt4,yt4 = tr.quad[1]

                    #export_nuke(xt1,yt1,xt2,yt2,xt3,yt3,xt4,yt4)
                    
                    pts2 = np.float32([[xt1,yt1],[xt2,yt2],[xt3,yt3],[xt4,yt4]])
                    M = cv2.getPerspectiveTransform(pts1,pts2)
                    
                    dst = cv2.warpPerspective(img_fg,M,(int(frame_width),int(frame_height)))                    
                    dstM = cv2.warpPerspective(mask,M,(int(frame_width),int(frame_height)))
                    
                    mask_inv = cv2.bitwise_not(dstM)
                    vis = cv2.bitwise_and(vis,vis,mask = mask_inv)

                    if self.off_info == 'off':
                        vis = cv2.add(vis,dst)
                        #vis = cv2.addWeighted(vis,1,dst,0.3,0)
                    else:
                        frame_counter = self.cap.get(cv2.cv.CV_CAP_PROP_POS_FRAMES)
                        cv2.putText(vis,str(frame_width)+' '+str(frame_height)+' '+'frame '+str(frame_counter),(20,50), font, 1,(255,0,0),2)
                    
                        cv2.circle(vis,(xt1,yt1), 5, (0,0,255), -1)
                        cv2.putText(vis,'track01 '+str(xt1)+' '+str(yt1),(xt1,yt1), font, 1,(0,255,255),2)

                        cv2.circle(vis,(xt2,yt2), 5, (0,0,255), -1)
                        cv2.putText(vis,'track02',(xt2,yt2), font, 1,(0,255,255),2)

                        cv2.circle(vis,(xt3,yt3), 5, (0,0,255), -1)
                        cv2.putText(vis,'track03',(xt3,yt3), font, 1,(0,255,255),2)

                        cv2.circle(vis,(xt4,yt4), 5, (0,0,255), -1)
                        cv2.putText(vis,'track04',(xt4,yt4), font, 1,(0,255,255),2)
                    
                        cv2.polylines(vis, [np.int32(tr.quad)], True, (255, 255, 255), 2)
                        for (x, y) in np.int32(tr.p1):
                            cv2.circle(vis, (x, y), 2, (0, 255, 0))
                        vis = cv2.add(vis,dst)

            self.rect_sel.draw(vis)
            cv2.imshow('plane', vis)
            ch = cv2.waitKey(1)
            if ch == ord(' '):
                self.paused = not self.paused
            if ch == ord('c'):
                self.tracker.clear()
            if ch == 27:
                break
class Window(QtGui.QWidget):
    
    def __init__(self):
        
        self.video_file=video_file
        self.image_file=image_file
        self.mask_file=mask_file
        self.off_info=off_info

        QtGui.QWidget.__init__(self)
        self.setWindowTitle('Control Panel')

        self.start_button = QtGui.QPushButton('Start',self)
        self.start_button.clicked.connect(self.startTrack)

        self.video_button = QtGui.QPushButton('Video file',self)
        self.video_button.clicked.connect(self.VideoFile)

        self.image_button = QtGui.QPushButton('Image file',self)
        self.image_button.clicked.connect(self.ImageFile)

        self.mask_button = QtGui.QPushButton('Mask file',self)
        self.mask_button.clicked.connect(self.MaskFile)
        
        self.off_info = QtGui.QCheckBox('Info markers', self)
        self.off_info.toggle()
        self.off_info.stateChanged.connect(self.OffInfo)

        #self.off_info = QtGui.QPushButton('Off info',self)
        #self.off_info.clicked.connect(self.OffInfo)

        vbox = QtGui.QVBoxLayout(self)
        vbox.addWidget(self.off_info)
        vbox.addWidget(self.video_button)
        vbox.addWidget(self.image_button)
        vbox.addWidget(self.mask_button)
        vbox.addWidget(self.start_button)

        self.setLayout(vbox)
        self.setGeometry(100,100,200,200)
        self.show()
        
    def OffInfo (self, state):
        if state == QtCore.Qt.Checked:
            self.off_info = 'on'
        else:
            self.off_info = 'off'    
        
        print self.off_info
           
    def VideoFile (self):
        self.video_file = QtGui.QFileDialog.getOpenFileName(self, 'Open video file')
        print "Video "+self.video_file
        
    def ImageFile (self):
        self.image_file = QtGui.QFileDialog.getOpenFileName(self, 'Open image file')
        print "Image "+self.image_file
        
    def MaskFile (self):
        self.mask_file = QtGui.QFileDialog.getOpenFileName(self, 'Open mask file')
        print "Mask "+self.mask_file
        
    def startTrack (self):
        import sys
        if len(self.video_file):
            video_src = self.video_file
        else: video_src = 0
        App(video_src,self.image_file,self.mask_file,self.off_info).run()


if __name__ == '__main__':

    import sys
    app = QtGui.QApplication(sys.argv)
    window = Window()
    sys.exit(app.exec_())
