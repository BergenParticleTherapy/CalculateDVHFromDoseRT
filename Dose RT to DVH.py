from __future__ import division
from __future__ import print_function

import numpy as np
from matplotlib import pyplot as plt
import matplotlib.patches as patches
import pydicom, os

try:
    from tkinter import *
    from tkinter import ttk
except:
    from Tkinter import *
    import ttk
    import tkFileDialog as filedialog

Gy = 1
dGy = 0.1
cGy = 0.01
mGy = 0.001
cc = 0.001

PROGRAM_VERSION = 1.11

# Changelog #
#############

# Version 1.1
# Added volumetric metrics such as Dx%, Vx% etc., as calculated from the DVHs in the DVH class
# Some error message supression (e.g. with empty volumes or empty slicewise plots)

# Version 1.11
# Explicit Python 2.x support through try...except wrappers

class Tooltip:
    '''
    It creates a tooltip for a given widget as the mouse goes on it.

    see:

    http://stackoverflow.com/questions/3221956/           what-is-the-simplest-way-to-make-tooltips-
           in-tkinter/36221216#36221216

    http://www.daniweb.com/programming/software-development/
           code/484591/a-tooltip-class-for-tkinter

    - Originally written by vegaseat on 2014.09.09.

    - Modified to include a delay time by Victor Zaccardo on 2016.03.25.

    - Modified
        - to correct extreme right and extreme bottom behavior,
        - to stay inside the screen whenever the tooltip might go out on
          the top but still the screen is higher than the tooltip,
        - to use the more flexible mouse positioning,
        - to add customizable background color, padding, waittime and
          wraplength on creation
      by Alberto Vassena on 2016.11.05.

      Tested on Ubuntu 16.04/16.10, running Python 3.5.2
    '''

    def __init__(self, widget,
                 bg='#FFFFEA',
                 pad=(5, 3, 5, 3),
                 text='widget info',
                 waittime=400,
                 wraplength=250):

        self.waittime = waittime  # in miliseconds, originally 500
        self.wraplength = wraplength  # in pixels, originally 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.onEnter)
        self.widget.bind("<Leave>", self.onLeave)
        self.widget.bind("<ButtonPress>", self.onLeave)
        self.bg = bg
        self.pad = pad
        self.id = None
        self.tw = None

    def onEnter(self, event=None):
        self.schedule()

    def onLeave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.show)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def show(self):
        def tip_pos_calculator(widget, label, 
                    tip_delta=(10, 5), pad=(5, 3, 5, 3)):

            w = widget

            s_width, s_height = w.winfo_screenwidth(), w.winfo_screenheight()

            width, height = (pad[0] + label.winfo_reqwidth() + pad[2],
                             pad[1] + label.winfo_reqheight() + pad[3])

            mouse_x, mouse_y = w.winfo_pointerxy()

            x1, y1 = mouse_x + tip_delta[0], mouse_y + tip_delta[1]
            x2, y2 = x1 + width, y1 + height

            x_delta = x2 - s_width
            if x_delta < 0:
                x_delta = 0
            y_delta = y2 - s_height
            if y_delta < 0:
                y_delta = 0

            offscreen = (x_delta, y_delta) != (0, 0)

            if offscreen:
                if x_delta:
                    x1 = mouse_x - tip_delta[0] - width

                if y_delta:
                    y1 = mouse_y - tip_delta[1] - height

            offscreen_again = y1 < 0  # out on the top
            if offscreen_again: y1 = 0

            return x1, y1

        bg = self.bg
        pad = self.pad
        widget = self.widget

        # creates a toplevel window
        self.tw = Toplevel(widget)

        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)

        win = Frame(self.tw,
                       background=bg,
                       borderwidth=0)
        label = Label(win,
                          text=self.text,
                          justify=LEFT,
                          background=bg,
                          relief=SOLID,
                          borderwidth=0,
                          wraplength=self.wraplength)

        label.grid(padx=(pad[0], pad[2]),
                   pady=(pad[1], pad[3]),
                   sticky=NSEW)
        win.grid()

        x, y = tip_pos_calculator(widget, label)

        self.tw.wm_geometry("+%d+%d" % (x, y))

    def hide(self):
        tw = self.tw
        if tw:
            tw.destroy()
        self.tw = None

class Options():
    def __init__(self):
        self.DVHFileType = StringVar(value = 'simple') # [ 'simple', 'eclipse' ]
        self.volumeType = StringVar(value = 'relative') # [ 'absolute', 'relative' ]
        self.includeRelativeDose = IntVar(value = 0) # [ 0, 1 ]
        self.doseSegmentation = DoubleVar(value = 0.1)
        self.doseUnit = StringVar(value = 'Gy') # mGy, cGy, dGy, Gy
        self.refineDoseMesh = IntVar(value = 2) # 1 -> 5?
        self.dataFolder = StringVar(value = ".")
        self.VxList = StringVar(value="20 50 60 70")
        self.DxList = StringVar(value="5 20 50")

        self.structureVariable = dict() # to be filled per instance
        self.maxDose = 100 # to be filled per instance

        self.vars = {'DVHFileType'          : self.DVHFileType,
                     'volumeType'           : self.volumeType,
                     'includeRelativeDose'  : self.includeRelativeDose,
                     'doseSegmentation'     : self.doseSegmentation,
                     'doseUnit'             : self.doseUnit,
                     'refineDoseMesh'       : self.refineDoseMesh,
                     'dataFolder'           : self.dataFolder,
                     'VxList'               : self.VxList,
                     'DxList'               : self.DxList }

    def loadOptions(self):
        read = False
        if os.path.exists('config.cfg'):
            with open("config.cfg", "r") as configFile:
                for line in configFile.readlines():
                    linesplit = line.rstrip().split(",")
                    var = linesplit[0]
                    value = linesplit[1]
                    if value:
                        read = True
                        if var in list(self.vars.keys()): 
                            self.vars[var].set(value)
        return read

    def saveOptions(self):
        with open("config.cfg","w") as configFile:
            for key, var in list(self.vars.items()):
                configFile.write("{},{}\n".format(key, var.get()))
                
class MainMenu(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent

        self.parent.protocol("WM_DELETE_WINDOW", self.myQuit)
        self.parent.title(f"Dose RT -> DVH converter {PROGRAM_VERSION} - Helge Pettersen")
        self.window = None

        self.wraplength = 250
        self.button_width = 25

        self.options = Options()
        res = self.options.loadOptions()

        if not os.path.exists("output"):
            os.makedirs("output")

        self.structureCheckbutton = dict()

        self.upperContainer = Frame(self, bd=5, relief=RIDGE, height=40)  # Title
        self.middleContainer = Frame(self, bd=5)
        self.bottomContainer = Frame(self, bd=20)

        self.middleLeftContainer = Frame(self.middleContainer, bd=5) # Load folders + options
        self.middleLeftUpperContainer = Frame(self.middleLeftContainer, bd=5) # Load folder tree (many RTDOSE)
        self.middleLeftLine1 = Frame(self.middleLeftContainer, bg="grey", relief=SUNKEN)
        self.middleLeftMiddleContainer = Frame(self.middleLeftContainer, bd=5) # Load individual files (single RTDOSE)
        self.middleLeftLine2 = Frame(self.middleLeftContainer, bg="grey", relief=SUNKEN)
        self.middleLeftLowerContainer = Frame(self.middleLeftContainer, bd=5) # Options
        self.middleRightLine = Frame(self.middleContainer, bg="grey", relief=SUNKEN)
        self.middleRightContainer = Frame(self.middleContainer, bd=5)
        self.middleRightUpperContainer = Frame(self.middleRightContainer, bd=5) # progress bar
        self.middleRightUpperLine = Frame(self.middleRightContainer, bd=5)
        self.middleRightLowerContainer = Frame(self.middleRightContainer, bd=5) # Structure window
        self.middleRightLowerLeftContainer = Frame(self.middleRightLowerContainer, bd=5)
        self.middleRightLowerMiddleContainer = Frame(self.middleRightLowerContainer, bd=5)
        self.middleRightLowerRightContainer = Frame(self.middleRightLowerContainer, bd=5)
        self.bottomLine = Frame(self.bottomContainer, bg="grey", relief=SUNKEN)
        self.bottomContainer1 = Frame(self.bottomContainer) # Action buttons

        # Output options
        self.dvhFileContainer = Frame(self.middleLeftLowerContainer)
        self.volumeTypeContainer = Frame(self.middleLeftLowerContainer)
        self.includeRelativeDoseContainer = Frame(self.middleLeftLowerContainer)
        self.doseSegmentationContainer = Frame(self.middleLeftLowerContainer)
        self.refineDoseMeshContainer = Frame(self.middleLeftLowerContainer)
        self.VxListContainer = Frame(self.middleLeftLowerContainer)
        self.DxListContainer = Frame(self.middleLeftLowerContainer)
        self.structureActionContainer = Frame(self.middleRightLowerContainer)

        self.upperContainer.pack(fill=X)
        self.middleContainer.pack(fill=Y)
        self.middleLeftContainer.pack(side=LEFT,fill='both', expand=1, anchor=N)
        self.middleLeftUpperContainer.pack(fill=X)
        self.middleLeftLine1.pack(fill=X, padx=5, pady=5)
        self.middleLeftMiddleContainer.pack(fill=X)
        self.middleLeftLine2.pack(fill=X, padx=5, pady=5)
        self.middleLeftLowerContainer.pack(fill=X)
        self.middleRightLine.pack(side=LEFT, fill=Y, padx=5, pady=5, expand=1)
        self.middleRightContainer.pack(side=LEFT,fill=Y)
        self.middleRightUpperContainer.pack(fill=X)
        self.middleRightUpperLine.pack(fill=X, padx=5, pady=5)
        self.middleRightLowerContainer.pack(anchor=N, fill=X)
        self.bottomLine.pack(fill=X, padx=5, pady=5, expand=1)
        self.bottomContainer.pack(fill=X, anchor=N, expand=1)
        self.bottomContainer1.pack(anchor=N, expand=1)

        Label(self.upperContainer,
              text=f'Dose RT -> DVH converter {PROGRAM_VERSION} - Helge pettersen').pack(anchor=N)

        self.loadFolderButton = Button(self.middleLeftUpperContainer, text='Load folder tree',
                                       command=self.loadFolderCommand, width=self.button_width)
        self.loadFolderButton.pack(anchor=N, pady=3)
        Tooltip(self.loadFolderButton, text='Loops through all subfolders in the indicated folders. For each subfolder '
                'containing two files starting with RD. and RS., load the two files and perform the DVH calculations. '
                'With this method, no structure selection is available (all are used), and it is not possible to visually '
                'inspect the slicewise content of the files.', wraplength=self.wraplength)

        self.loadRSRDFileButton = Button(self.middleLeftMiddleContainer, text='Load RS+RD file pair',
                                       command=self.loadFileCommand, width=self.button_width)
        self.loadRSRDFileButton.pack(anchor=N, pady=3)

        Tooltip(self.loadRSRDFileButton, text='Load a single Dose RT instance from a RS + RD file pair. Structure selection '
                ' and visual inspection of the files are possible before storing to a DVH CSV file.', wraplength=self.wraplength)

        Label(self.middleLeftLowerContainer, text='OPTIONS', font=('Helvetica', 10)).pack(anchor=N)

        self.dvhFileContainer.pack(anchor=W)
        Label(self.dvhFileContainer, text='DVH output type: ').pack(side=LEFT, anchor=W)
        for mode in ['simple', 'eclipse']:
            Radiobutton(self.dvhFileContainer, text=mode, variable=self.options.DVHFileType, value=mode).pack(side=LEFT, anchor=W)
        Tooltip(self.dvhFileContainer, text='Simple is a stripped CSV file with headers for each patient / structure. Eclipse-type '
                'is a single file per patient, but containing some metadata and all the structures.', wraplength=self.wraplength)

        self.volumeTypeContainer.pack(anchor=W)
        Label(self.volumeTypeContainer, text='Volume output: ').pack(side=LEFT, anchor=W)
        for text, mode in [['Absolute vol [cc]', 'absolute'], ['Relative vol [%]', 'relative']]:
            Radiobutton(self.volumeTypeContainer, text=text, variable=self.options.volumeType, value=mode).pack(side=LEFT, anchor=W)

        """
        self.includeRelativeDoseContainer.pack(anchor=W)
        Label(self.includeRelativeDoseContainer, text='Include relative dose: ').pack(side=LEFT, anchor=W)
        for text, mode in [['Yes', 1], ['No', 0]]:
            Radiobutton(self.includeRelativeDoseContainer, text=text, variable=self.options.includeRelativeDose, value=mode).pack(side=LEFT, anchor=W)
        """
    
        self.doseSegmentationContainer.pack(anchor=W)
        Label(self.doseSegmentationContainer, text='Dose segmentation [Gy]: ').pack(side=LEFT, anchor=W)
        Entry(self.doseSegmentationContainer, textvariable=self.options.doseSegmentation, width=5).pack(side=LEFT)
        Tooltip(self.doseSegmentationContainer, text='Dose segmentation in the DVH files, in units of Gy.', wraplength=self.wraplength)

        self.refineDoseMeshContainer.pack(anchor=W)
        Label(self.refineDoseMeshContainer, text='Dose Mesh Refinement Factor: ').pack(side=LEFT, anchor=W)
        for mode in range(1,6):
            Radiobutton(self.refineDoseMeshContainer, text=mode, variable=self.options.refineDoseMesh, value=mode).pack(side=LEFT, anchor=W)
        Tooltip(self.refineDoseMeshContainer, text='During the dose summation, a ray tracing operation is performed to locate the RD voxels '
                'inside each structure. With a factor 1, the actual voxels are each evaluated (a voxel is included if it includes the '
                'structure delineation). At higher factors, each voxel is split in x/y by that factor, increasing the resolution -- '
                ' as well as the calculation time.', wraplength=self.wraplength)

        self.VxListContainer.pack(anchor=W)
        Label(self.VxListContainer, text='Evaluate V[D1 D2 ... DN]Gy: ').pack(side=LEFT, anchor=W)
        Entry(self.VxListContainer, textvariable=self.options.VxList, width=15).pack(side=LEFT)
        Tooltip(self.VxListContainer, text='Input a space-separated list (\'10 50 60\') with dose [Gy] values to evaluate the '
                'relative volume at. The final, slice-summed per-structure DVH curve is used for the calculation. '
                'The output is given in the \'eclipse\' text output. For more advanced dose metrics, such as gEUD etc., '
                'see the DVH Tool (v1.3) program by Helge Pettersen.', wraplength=self.wraplength)

        self.DxListContainer.pack(anchor=W)
        Label(self.DxListContainer, text='Evaluate D[V1 V2 ... VN]%:   ').pack(side=LEFT, anchor=W)
        Entry(self.DxListContainer, textvariable=self.options.DxList, width=15).pack(side=LEFT)
        Tooltip(self.DxListContainer, text='Input a space-separated list (\'10 20 30\') with volume fraction [%] '
                'values to evaluate the dose at. The final, slice-summed per-structure DVH curve is used for the calculation. '
                'The output is given in the \'eclipse\' text output. For more advanced dose metrics, such as gEUD etc., '
                'see the DVH Tool (v1.3) program by Helge Pettersen.', wraplength=self.wraplength)

        self.progress = ttk.Progressbar(self.middleRightUpperContainer, orient=HORIZONTAL, maximum=100, mode='determinate')
        self.progress.pack(fill=X, pady=3)

        Label(self.middleRightLowerContainer, text='STRUCTURES', font=('Helvetica',10)).pack(anchor=N)
        
        self.structureActionContainer.pack(anchor=W)
        self.structureActionCheckAllButton = Button(self.structureActionContainer, text='Check all', command=self.structureCheckAllCommand,
               width=self.button_width, state=DISABLED)
        self.structureActionUncheckAllButton = Button(self.structureActionContainer, text='Uncheck all', command=self.structureUncheckAllCommand,
               width=self.button_width, state=DISABLED)

        self.structureActionCheckAllButton.pack(side=LEFT)
        self.structureActionUncheckAllButton.pack(side=LEFT)

        self.middleRightLowerLeftContainer.pack(anchor=N, side=LEFT, fill=X)
        self.middleRightLowerMiddleContainer.pack(anchor=N, side=LEFT, fill=X)
        self.middleRightLowerRightContainer.pack(anchor=N, side=LEFT, fill=X)

        # PUT STRUCTURES HERE WHEN / IF THEY ARE LOADED FROM SINGLE RS FILE

        self.buttonPlotRTDoseSlicewise = Button(self.bottomContainer1, text='Plot RT dose + DVH per slice',
                                command=self.plotRTDoseSlicewiseCommand, width=self.button_width, state=DISABLED)
        self.buttonPlotDVH = Button(self.bottomContainer1, text='Plot DVH',
                                command=self.plotDVHCommand, width=self.button_width, state=DISABLED)
        self.buttonSaveDVH = Button(self.bottomContainer1, text='Save DVH file(s)', command=self.saveDVHCommand,
                                    width=self.button_width, state=DISABLED)
        self.buttonQuit = Button(self.bottomContainer1, text='Exit', command=self.myQuit, width=self.button_width)

        for button in [self.buttonPlotRTDoseSlicewise, self.buttonPlotDVH, self.buttonSaveDVH, self.buttonQuit]:
            button.pack(side=LEFT, anchor=N, padx=5, pady=5)

        self.pack()

    def myQuit(self):
        self.options.saveOptions()
        self.parent.destroy()
        self.quit()

    def loadFolderCommand(self):
        self.imagePair = []

        dataFolder = filedialog.askdirectory(title="Get root directory for RS/RD file pairs", initialdir=self.options.dataFolder.get())
        if not dataFolder:
            print("No directory selected, aborting.")
            return

        self.options.dataFolder.set(dataFolder)
        
        for root, d, f, in os.walk(dataFolder): # loop through folders
            RSfile = None
            RDfile = None
            try:
                for filename in f: # loop through files
                    if 'RD' in filename:
                        RDfile = f"{root}/{filename}"
                    elif 'RS' in filename:
                        RSfile = f"{root}/{filename}"

                if not RSfile or not RDfile:
                    continue
                
                self.imagePair.append(Series(rd=RDfile, rs=RSfile))

            except Exception as e:
                print(f"Could not process RD/RS files in {root}: {e}")

        print(f"Loading structures from {len(self.imagePair)} RD/RS pairs...")
        idx_sum = 0
        nStructures = 0
        for imagePair in self.imagePair:
            nStructures += len(imagePair.rs.ROIContourSequence)
            
        self.progress['maximum'] = nStructures
        
        for imagePair in self.imagePair:
            imagePair.loadStructures(self.progress)

            structureContainer = [self.middleRightLowerLeftContainer,
                                  self.middleRightLowerMiddleContainer,
                                  self.middleRightLowerRightContainer]
            
            for idx, structureName in enumerate(imagePair.listOfStructures):
                if structureName in self.options.structureVariable.keys():
                    continue
                
                self.options.structureVariable[structureName] = IntVar(value=1)
                self.structureCheckbutton[structureName] = Checkbutton(structureContainer[idx_sum%3], text=structureName,
                                                                variable=self.options.structureVariable[structureName])
                self.structureCheckbutton[structureName].pack(anchor=NW)
                idx_sum += 1

            self.structureActionCheckAllButton['state'] = 'normal'
            self.structureActionUncheckAllButton['state'] = 'normal'

            self.buttonPlotDVH['state'] = 'normal'
            self.buttonPlotRTDoseSlicewise['state'] = 'normal'
            self.buttonSaveDVH['state'] = 'normal'

        self.progress['value'] = 0

    def loadFileCommand(self):
        fileList = filedialog.askopenfilenames(title='Get RD+RS files', initialdir=self.options.dataFolder.get())
        if not fileList:
            print("No files selected, aborting.")
            return

        self.options.dataFolder.set(fileList[0])

        try:
            RSfile = None
            RDfile = None
            for file in fileList:
                if 'RD' in file:
                    RDfile = file

                elif 'RS' in file:
                    RSfile = file

            if not RSfile or not RDfile:
                print("Could not identify files, try naming then with \'RS\' and \'RD\' in filename")
                return

            self.imagePair = [Series(rd=RDfile, rs=RSfile)]

            self.progress['maximum'] = len(self.imagePair[0].rs.ROIContourSequence)
            
            self.imagePair[0].loadStructures(self.progress)

            structureContainer = [self.middleRightLowerLeftContainer,
                                  self.middleRightLowerMiddleContainer,
                                  self.middleRightLowerRightContainer]
            
            for idx, structureName in enumerate(self.imagePair[0].listOfStructures):
                self.options.structureVariable[structureName] = IntVar(value=1)
                self.structureCheckbutton[structureName] = Checkbutton(structureContainer[idx%3], text=structureName,
                                                                variable=self.options.structureVariable[structureName])
                self.structureCheckbutton[structureName].pack(anchor=NW)

            self.structureActionCheckAllButton['state'] = 'normal'
            self.structureActionUncheckAllButton['state'] = 'normal'

            self.buttonPlotDVH['state'] = 'normal'
            self.buttonPlotRTDoseSlicewise['state'] = 'normal'
            self.buttonSaveDVH['state'] = 'normal'
            
        except Exception as e:
            print("Could not read files, aborting.",)
            print(f"Error message: {e}")
            return

    def plotRTDoseSlicewiseCommand(self): # ONLY AVAILABLE WITH ONE RD/RS PAIR
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20,10))
        X = self.imagePair[0].getDoseImage()
        tracker = IndexTracker(ax1, ax2, X, self.imagePair[0], self.options)
        fig.canvas.mpl_connect('scroll_event', tracker.onscroll)
        plt.show()

    def plotDVHCommand(self): # MAKE MULTIPLE IMAGES WITH >1 RD/RS PAIRS
        activeStructures = [k for k,v in self.options.structureVariable.items() if v.get()]
        self.progress['maximum'] = len(activeStructures) * sum([int(k.rd.NumberOfFrames) for k in self.imagePair])
        
        for imagePair in self.imagePair:
            img = imagePair.getDoseImage()
            sh = np.shape(img)

            maxDose = imagePair.maxDose
            self.options.maxDose = maxDose


            structureDose = dict()        
            dose = np.arange(0, maxDose, self.options.doseSegmentation.get())
            structureVolume = { s : np.zeros(dose.shape) for s in activeStructures }

            for z in range(sh[0]):
                for structure in activeStructures:
                    self.progress.step(1)
                    self.progress.update_idletasks()
                    
                    contours = imagePair.getStructuresInImageCoordinates(structure, z)
                    for contourX, contourY in zip(*contours):
                        linearContour = LinearContour(self.options)
                        linearContour.addLines(np.dstack((contourX, contourY))[0])
                        dose, structureVolume[structure] = linearContour.getDVH(img[z,:,:], imagePair.voxelVolume, structureVolume[structure])


            fig = plt.figure()
            for structure in activeStructures:
                if self.options.volumeType.get() == 'relative':
                    if structureVolume[structure][0] > 0:
                        structureVolume[structure] *= 100 / structureVolume[structure][0]
                    else:
                        print(f"Cannot normalize volume for empty structure {structure}.")
                    plt.ylabel("Volume [%]")
                else:
                    structureVolume[structure] *= cc
                    plt.ylabel("Volume [cc]")

                plt.title(f"DVH: PatientName: {imagePair.rs.PatientName}, PatientID: {imagePair.rs.PatientID}")
                plt.xlabel("Dose [Gy]")
                plt.plot(dose, structureVolume[structure], label=structure)
        
            plt.legend()
        self.progress['value'] = 0
        plt.show()
        

    def saveDVHCommand(self):
        nFiles = 0
        activeStructures = [k for k,v in self.options.structureVariable.items() if v.get()]
        self.progress['maximum'] = len(activeStructures) * sum([int(k.rd.NumberOfFrames) for k in self.imagePair])

        for imagePair in self.imagePair:
            img = imagePair.getDoseImage()
            sh = np.shape(img)

            maxDose = imagePair.maxDose
            self.options.maxDose = maxDose

            structureDose = dict()
            dose = np.arange(0, maxDose, self.options.doseSegmentation.get())
            structureVolume = { s : np.zeros(dose.shape) for s in activeStructures }

            for z in range(sh[0]):
                for structure in activeStructures:
                    self.progress.step(1)
                    self.progress.update_idletasks()
                    
                    contours = imagePair.getStructuresInImageCoordinates(structure, z)
                    for contourX, contourY in zip(*contours):
                        linearContour = LinearContour(self.options)
                        linearContour.addLines(np.dstack((contourX, contourY))[0])
                        dose, structureVolume[structure] = linearContour.getDVH(img[z,:,:], imagePair.voxelVolume, structureVolume[structure])

            eclipse_output = ""
                
            eclipse_output += f"Patient Name\t\t: {imagePair.rs.PatientName}\n"
            eclipse_output += f"Patient ID\t\t: {imagePair.rs.PatientID}\n"
            eclipse_output += f"Comment\t\t: Made by RD2DVH.py version {PROGRAM_VERSION} by Helge Pettersen\n"
            eclipse_output += "Type\t\t: Cumulative Dose Volume Histogram\n"
            
            for structure in activeStructures:
                csv_output = ""
                eclipse_output += f"\nStructure: {structure}\n"
                eclipse_output += f"Approval Status: {imagePair.rs.ApprovalStatus}\n"
                eclipse_output += f"Volume [cc]: {structureVolume[structure][0]*cc:.3f}\n"
                
                if structureVolume[structure][0] > 0:
                    DxList = [ float(k) for k in self.options.DxList.get().split(" ") ]
                    VxList = [ float(k) for k in self.options.VxList.get().split(" ") ]

                    dvhCalculator = DVH(dose, structureVolume[structure], self.options)
                    DxListEvaluated = [ dvhCalculator.getDoseAtVolume(k) for k in DxList ]
                    VxListEvaluated = [ dvhCalculator.getVolumeAtDose(k) for k in VxList ]
                
                    eclipse_output += "\n".join([f"D{Din}% = {Dout:.2f} Gy" for Din, Dout in zip(DxList, DxListEvaluated)])
                    eclipse_output += "\n"
                    eclipse_output += "\n".join([f"V{Vin} Gy = {Vout:.2f}%" for Vin, Vout in zip(VxList, VxListEvaluated)])
                    eclipse_output += "\n"

                eclipse_output += "\n"
                if self.options.volumeType.get() == 'relative':
                    if structureVolume[structure][0] > 0:
                        structureVolume[structure] *= 100 / structureVolume[structure][0]
                        eclipse_output += "Dose [Gy]\t\tVolume [%]\n"
                        csv_output += "Dose [Gy],Volume [%]\n"
                    else:
                        print(f"Cannot normalize volume for empty structure {structure}.")
                        structureVolume[structure] *= cc
                        eclipse_output += "Dose [Gy]\t\tVolume [cc]\n"
                        csv_output += "Dose [Gy],Volume [%]\n"
                else:
                    structureVolume[structure] *= cc
                    eclipse_output += "Dose [Gy]\t\t\tVolume [cc]\n"
                    csv_output += "Dose [Gy],Volume [cc]\n"
                    
                for line in zip(dose,structureVolume[structure]):
                    eclipse_output += f"{float(line[0]):8.5f}\t\t{float(line[1]):8.5f}\n"
                    csv_output += f"{float(line[0]):8.5f},{float(line[1]):8.5f}\n"

                if self.options.DVHFileType.get() == "simple":
                    with open(f"output/{imagePair.rs.PatientName}_{structure}.csv", 'w') as csv_file:
                        csv_file.write(csv_output)
                        nFiles += 1

            if self.options.DVHFileType.get() == "eclipse":
                with open(f"output/{imagePair.rs.PatientName}.txt", 'w') as eclipse_file:
                    eclipse_file.write(eclipse_output)
                    nFiles += 1

        s = nFiles>1 and "s" or ""
        self.progress['value'] = 0
        print(f"Saved {nFiles} file{s}.")
                    
    def structureCheckAllCommand(self):
        for check in self.options.structureVariable.values():
            check.set(1)

    def structureUncheckAllCommand(self):
        for check in self.options.structureVariable.values():
            check.set(0)

class IndexTracker(object):
    def __init__(self, ax1, ax2, X, images, options):
        self.ax1 = ax1
        self.ax2 = ax2
        self.images = images
        self.options = options
        self.lines = list()
        self.ax1.set_title('use scroll wheel to navigate images')

        self.X = X
        self.slices, cols, rows = X.shape
        self.ind = self.slices//2
        self.ind = 96
        
        self.im = self.ax1.imshow(self.X[self.ind, :, :], cmap="gray")
        self.update()
        

    def onscroll(self, event):
        if event.button == 'up':
            self.ind = (self.ind + 1) % self.slices
        else:
            self.ind = (self.ind - 1) % self.slices
        self.update()

    def update(self):
        self.im.set_data(self.X[self.ind, :, :])
        self.ax1.set_ylabel('slice %s' % self.ind)

        self.ax1.lines = []
        self.ax2.lines = []

        colors = ['r', 'g', 'b', 'y', 'c', 'm', 'orange', 'lightcoral',
                  'peachpuff', 'olive', 'gold', 'navy', 'sienna', 'tan', 'crimson',
                  'lime', 'goldenrod', 'moccasin', 'beige', 'tomato', 'mistyrose', 'darksalmon',
                  'navajowhite', 'darkorange', 'snow', 'teal', 'deeppink', 'orchid']
        
        colStruct = dict(zip(self.images.listOfStructures, colors))

        activeStructures = [k for k,v in self.options.structureVariable.items() if v.get()]
        activePlot = False
        
        for structure in activeStructures:            
            contours = self.images.getStructuresInImageCoordinates(structure, self.ind)
            lastVolume = None
            
            for contourX, contourY in zip(*contours):
                self.ax1.plot(contourX, contourY, color=colStruct[structure])

                linearContour = LinearContour(self.options)
                linearContour.addLines(np.dstack((contourX, contourY))[0])
                dose, volume = linearContour.getDVH(self.X[self.ind, :, :], self.images.voxelVolume, lastVolume)
                lastVolume = volume

            if len(contours[0]):
                if self.options.volumeType.get() == 'absolute':
                    volume *= cc # absolute dose in cc
                    self.ax2.set_ylabel("Volume [cc]")
                else:
                    volume *= (100 /  volume[0]) # normalized dose in %
                    self.ax2.set_ylabel("Volume [%]")
                    
                self.ax2.plot(dose, volume, color=colStruct[structure], label=structure)
                self.ax2.set_xlabel(f"Dose [{self.images.rd[0x3004,0x2].value.capitalize()}]")
                activePlot = True
                
        if activePlot:
            plt.legend()
            
        self.im.axes.figure.canvas.draw()

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

class DVH:
    def __init__(self, dose, volume, options):
        self.dose = dose
        if volume[0] == 0:
            print("Cannot calculate DVH statistics on a zero-volume object")
        else:
            self.volume = volume * 100 / volume[0]
        self.options = options

    def getVolumeAtDose(self, atDose):
        if np.sum(self.volume[self.dose > atDose]) == 0:
            return 0

        return np.interp(atDose, self.dose, self.volume)

    def getDoseAtVolume(self, atVolume):
        return np.interp(atVolume, self.volume[::-1], self.dose[::-1])

    def calculateGEUD(self, n):
        # If more advanced dose metrics are needed, use DVH Tool v1.3 by Helge Pettersen
        pass

class LinearContour:
    def __init__(self, options):
        self.lines = list()
        self.xmin = self.ymin = 1e5
        self.xmax = self.ymax = -1e5
        self.meshFactor = 1
        self.options = options

    def addLines(self, listOfPoints):
        # Remember to scale the structures as well as the dose mesh
        listOfPoints = [[k[0]*self.meshFactor, k[1]*self.meshFactor] for k in listOfPoints]
        
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

    def getDVH(self, image, voxelVolume, lastVolume):
        # Resize image to evaluate at more points
        sh = np.shape(image)
        sh = [sh[0]*self.meshFactor, sh[1]*self.meshFactor]
        largerImage = np.zeros(sh)
        for x in np.arange(sh[1]):
            for y in np.arange(sh[0]):
                largerImage[y,x] = image[y//self.meshFactor, x//self.meshFactor]

        contourMap = self.getListOfPixelsInContour(largerImage)
        contourImage = largerImage * contourMap
        voxelVolume /= self.meshFactor**2

        maxDose = self.options.maxDose
        doseRange = np.arange(0, maxDose, self.options.doseSegmentation.get())
        
        if type(lastVolume) != type(None):
            volumeRange = lastVolume
        else:
            volumeRange = np.zeros(np.shape(doseRange))
        
        for idx, dose in enumerate(doseRange):
            isAboveDose = contourImage > dose
            absoluteVolume = voxelVolume * np.sum(contourMap[isAboveDose])
            volumeRange[idx] += absoluteVolume

        return doseRange, volumeRange

class Series:
    def __init__(self, rd = None, rs = None, progress=None):
        self.rs = pydicom.dcmread(rs)
        self.rd = pydicom.dcmread(rd)
        stlist = self.rd[self.rd.FrameIncrementPointer].value
        self.sliceThickness = float(stlist[1]) - float(stlist[0])
        self.voxelVolume = self.sliceThickness * self.rd.PixelSpacing[0] * self.rd.PixelSpacing[1]
        self.doseImage = self.rd.pixel_array * self.rd[0x3004,0xE].value
        self.maxDose = round(np.max(self.doseImage)*1.05+5,-1)
        self.contours = dict()

    def loadRBE(self, progress = None):
        pass

    def loadLET(self, progress = None):
        pass

    def recalculateDose(self, progress = None):
        pass

    def loadStructures(self, progress = None):
        structureDict = dict()
        for seq in self.rs.StructureSetROISequence:
            structureDict[seq[0x3006, 0x22].value] = seq[0x3006, 0x26].value

        self.listOfStructures = structureDict.values()

        for structureName in structureDict.values():
            self.contours[structureName] = list()

        for idx, seq in enumerate(self.rs.ROIContourSequence): # Loop over the different structures
            if progress:
                progress.step(1)
                progress.update_idletasks()
            
            thisStructure = structureDict[seq.ReferencedROINumber]
            
            if 'ContourSequence' in seq:
                for cont in seq.ContourSequence: # Loop over slices
                    cd = cont.ContourData
                    self.contours[thisStructure].append(np.reshape(cd, (len(cd)//3, 3)))

    def getStructuresInImageCoordinates(self, structureName, zIdx):
        cListX, cListY = list(), list()
        zAbsolute = zIdx * self.sliceThickness + float(self.rd.ImagePositionPatient[2])
                
        for contourZ in self.contours[structureName]:
            if abs(contourZ[0,2] - zAbsolute) > 0.1: continue
            cListX.append((contourZ[:,0] - self.rd.ImagePositionPatient[0]) / self.rd.PixelSpacing[0])
            cListY.append((contourZ[:,1] - self.rd.ImagePositionPatient[1]) / self.rd.PixelSpacing[1])
        
        return cListX, cListY

    def getImageDate(self):
        return self.ds[0x8,0x20].value

    def getDoseImage(self):
        return self.doseImage

root = Tk()
mainmenu = MainMenu(root)
root.mainloop()
