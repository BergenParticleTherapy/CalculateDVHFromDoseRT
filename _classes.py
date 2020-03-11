import numpy as np
from matplotlib import pyplot as plt
import matplotlib.patches as patches
import pydicom, os


class Line:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.x1, self.y1 = x1, y1        
        
        if (y1 == y0):  self.dxdy = 0
        else:           self.dxdy = (x1 - x0) / (y1 - y0)
        
        if (x1 == x0):  self.dydx = 1e5
        else:           self.dydx = (y1 - y0) / (x1 - x0)

    def findIntercept(self, x=None, y=None):
        if x:
            if self.x0 < x <= self.x1:
                return (x-self.x0) * self.dydx + self.y0
            elif self.x1 < x <= self.x0:
                return (x-self.x0) * self.dydx + self.y0
    
        elif y:
            if self.y0 < y <= self.y1:
                return (y-self.y0) * self.dxdy + self.x0
            elif self.y1 < y <= self.y0:
                return (y-self.y0) * self.dxdy + self.x0
            
        return None

class LinearContour:
    def __init__(self, dicomTranslation, pixelSpacing):
        self.lines = list()
        self.dicomTranslation = dicomTranslation
        self.pixelSpacing = pixelSpacing
        self.xmin = self.ymin = self.xmax = self.ymax = None

    def addLines(self, listOfPoints):
        lastPoint = listOfPoints[-1]
        self.xmin = self.xmax = lastPoint[0]
        self.ymin = self.ymax = lastPoint[1]
        
        for point in listOfPoints:
            self.xmin = min(self.xmin, point[0])
            self.ymin = min(self.ymin, point[1])
            self.xmax = max(self.xmax, point[0])
            self.ymax = max(self.ymax, point[1])
            
            self.lines.append(Line(*lastPoint, *point))
            lastPoint = point

    def getInterceptingLines(self, x=None, y=None):
        interceptPoints = []
        for line in self.lines:
            intercept = line.findIntercept(x,y)
            if intercept:
                interceptPoints.append(intercept)

        return interceptPoints   

    def findPixelInsideContourColumn(self, x, sh):
        column = np.zeros(sh[0])
        ray = self.getInterceptingLines(x, None)

        yRangesInsideContour = []
        for k in range(int((len(ray)+1)/2)):
            yRangesInsideContour.append([int(ray[2*k]), int(ray[2*k+1]+1)])
        
        for yFrom, yTo in yRangesInsideContour:
            ymin, ymax = sorted([yFrom, yTo])
            column[ymin:ymax] = True

        return column
    
    def getListOfPixelsInContour(self, image):
        sh = np.shape(image)
        contourMap = np.zeros(sh, dtype="bool")
        
        for x in range(int(self.xmin), int(self.xmax+1)):
            contourMap[:,x] = self.findPixelInsideContourColumn(x, sh)

        return contourMap

class Series:
    def __init__(self, path = None, zpos = None,
                 structure = None, translation = None):
        self.path = path
        self.zpos = zpos
        self.structure = structure
        self.translation = translation
        self.dicomTranslation = None

        self.rs = None
        self.ds = None
        self.image = None
        self.imageWEPL = None
        self.contourWEPL = list()
        self.pixelSpacing = None
        self.imageUID = None
        self.contours = list()

    def loadImages(self):
        fDS, fRS = list(), list()
        for (dirpath, dirnames, filenames) in os.walk(self.path):
            fDS += [os.path.join(dirpath, file) for file in filenames if "CT" in file]
            fRS += [os.path.join(dirpath, file) for file in filenames if "RS" in file]

        DS = [[x, pydicom.dcmread(x, stop_before_pixels=True)] for x in fDS]
        self.rs = pydicom.dcmread(fRS[0])

        if self.zpos:
            for images in DS:
                if abs(images[1][0x20,0x32][2] + self.translation[2] - self.zpos) <= 1:
                    self.ds = pydicom.dcmread(images[0])
                    break
        else:
            self.ds = pydicom.dcmread(DS[0][0])
        
        self.pixelSpacing = float(self.ds.PixelSpacing[0])
        self.dicomTranslation = [float(k) for k in self.ds[0x20,0x32]]
        self.imageUID = self.ds[0x8, 0x18].value
        self.image = np.array(self.ds.pixel_array, dtype='int')
        self.image += int(self.ds.RescaleIntercept)

    def loadStructures(self):
        contourIdxList = list()
        imageIdxList = list()

        for idx, seq in enumerate(self.rs.StructureSetROISequence):
            if seq[0x3006,0x26].value == self.structure:
                contourIdxList.append(idx)

        for contourIdx in contourIdxList:
            for idx, seq in enumerate(self.rs.ROIContourSequence[contourIdxList[0]].ContourSequence):
                if seq[0x3006,0x16][0][0x8,0x1155].value == self.imageUID:
                    imageIdxList.append(idx)

        if len(imageIdxList) > len(contourIdxList):
            contourIdxList *= len(imageIdxList)
        contourImageIdx = zip(contourIdxList, imageIdxList)

        for contourIdx, imageIdx in contourImageIdx:
            contour  = self.rs.ROIContourSequence[contourIdx].ContourSequence[imageIdx].ContourData
            self.contours.append(np.reshape(contour, (len(contour)//3, 3)))

    def getStructuresInImageCoordinates(self):
        cListX, cListY = list(), list()
        
        for contour in self.contours:
            x = (contour[:,0] - self.dicomTranslation[0]) / self.pixelSpacing
            y = (contour[:,1] - self.dicomTranslation[1]) / self.pixelSpacing
            cListX.append(x)
            cListY.append(y)
    
        return cListX, cListY

    def convertImageToRSP(self):
        # HU - RSP calibration (use data from Schneider et al., PMB 41(1) (1996)
        fHigh = lambda x: 1.06037 + 0.00046761*x
        fLow  = lambda x: 1.02365 + 0.00100547*x
        
        threshold = self.image >= 200

        self.imageRSP = np.where(threshold, fHigh(self.image), 0) \
                        + np.where(~threshold, fLow(self.image), 0)
        
        return self.imageRSP

    def convertImageToWEPL(self):
        self.imageWEPL = np.zeros(self.image.shape)
        for x in range(self.image.shape[0]):
            self.imageWEPL[:,x] = self.imageRSP[:,x] * self.pixelSpacing
            if x > 0: self.imageWEPL[:,x] += self.imageWEPL[:,x-1]

        return self.imageWEPL

    def createWEPLcurve(self):
        for contourX, contourY in zip(*self.getStructuresInImageCoordinates()):
            for xi, yi in zip(contourX, contourY):
                self.contourWEPL.append(self.imageWEPL[int(yi), int(xi)])

        return self.contourWEPL

    def getImageDate(self):
        return self.ds[0x8,0x20].value            
