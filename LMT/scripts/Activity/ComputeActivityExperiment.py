'''
Created by Nicolas Torquet at 18/11/2024
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''


'''
This script computes the activity (distance travelled) of each animal for a given timebin.

Setup :
Transparent cage of 50 x 50 cm with a new sawdust bottom. 
Kinect at 63 cm high from the floor.
'''

import sqlite3
from lmtanalysis.Measure import oneMinute, oneHour
from Util import getDatetimeFromFrame, getNumberOfFrames
from Parameters import getAnimalTypeParameters
from ZoneArena import getZoneCoordinatesFromCornerCoordinatesOpenfieldArea
from lmtanalysis.AnimalType import AnimalType
from Animal_LMTtoolkit import AnimalPoolToolkit
from FileUtil import getFilesToProcess
import json
import matplotlib.pyplot as plt
from Event import EventTimeLine


class ActivityExperiment:
    def __init__(self, file, tStartPeriod=1, durationPeriod=24, timebin=10):
        '''
        :param file: path of the experiment file
        :param animalType: the animalType to get animalType's parameters
        :param tStartExperiment: the first frame of the investigated period
        :param durationExperiment: duration in hours of the experiment
        :param timebin: timebin in minutes to compute the distance travelled
        '''
        # global animalType
        self.file = file
        self.name = file.split('.sqlite')[0].split('\\')[-1].split("/")[-1]
        self.animalType = animalType
        self.tStartPeriod = tStartPeriod   # framenumber
        self.durationPeriod = durationPeriod*oneHour  # duration in number of frame
        self.tStopFramePeriod = self.tStartPeriod+self.durationPeriod    # convert in framenumber
        self.durationPeriod = durationPeriod    # duration in hours
        self.durationPeriodInFrame = durationPeriod*oneMinute    # duration in number of frame
        self.timebin = timebin # timebin in minutes
        self.timebinInFrame = timebin*oneMinute # timebin in number of frame
        # Get start datetime and end datetime for metadata
        connection = sqlite3.connect(self.file)
        self.startDatetime = getDatetimeFromFrame(connection, self.tStartPeriod)
        self.endDatetime = getDatetimeFromFrame(connection, self.tStopFramePeriod)
        connection.close()
        if self.endDatetime is None:
            self.tStopFramePeriod = getNumberOfFrames(file)
            connection = sqlite3.connect(self.file)
            self.endDatetime = getDatetimeFromFrame(connection, self.tStopFramePeriod)
            connection.close()
        self.numberOfTimeBin = (self.tStopFramePeriod - self.tStartPeriod) / self.timebinInFrame
        # Get animalPool to compute activity
        self.pool = self.extractActivityPerAnimalStartEndInput()
        self.animals = {}
        for animal in self.pool.animalDictionary:
            print(self.pool.animalDictionary[animal])
            self.animals[self.pool.animalDictionary[animal].RFID] = {
                'id': self.pool.animalDictionary[animal].baseId,
                'name': self.pool.animalDictionary[animal].name,
                'rfid': self.pool.animalDictionary[animal].RFID,
                'genotype': self.pool.animalDictionary[animal].genotype,
                'sex': self.pool.animalDictionary[animal].sex,
                'age': self.pool.animalDictionary[animal].age,
                'strain': self.pool.animalDictionary[animal].strain,
                'treatment': self.pool.animalDictionary[animal].treatment
            }

        ''' 
        Cage parameters default to animalType parameters but can be modified
        cage coordinates have this format:
        {'xa': 168, 'xb': 343, 'ya': 120, 'yb': 296}
        '''
        self.parameters = getAnimalTypeParameters(animalType)
        self.wholeCageCoordinates = getZoneCoordinatesFromCornerCoordinatesOpenfieldArea(self.animalType)

        self.activity = {}
        self.totalDistance = {}
        self.results = {}
        self.reorganizedResults = {}


    def getName(self):
        return self.name

    def setWholeCageCoordinates(self, wholeCageCoordinates):
        '''
        :param wholeCageCoordinates: format like {'xa': 168, 'xb': 343, 'ya': 120, 'yb': 296}
        '''
        self.wholeCageCoordinates = wholeCageCoordinates

    def getWholeCageCoordinates(self):
        return self.wholeCageCoordinates

    def getMetadata(self):
        animalTypeString = str(self.animalType).split('.')[1]
        metadata = {
            'animalType': animalTypeString,
            'wholeCageCoordinates': self.wholeCageCoordinates,
            'startFrame': self.tStartPeriod,
            'durationExperiment': self.durationPeriod,
            'timeBin': self.timebin,
            'startDatetime': self.startDatetime.strftime("%d/%m/%Y %H:%M:%S.%f"),
            'endDatetime': self.endDatetime.strftime("%d/%m/%Y %H:%M:%S.%f")
        }
        return metadata

    def extractActivityPerAnimalStartEndInput(self):
        '''
        Load animals information and detections into an AnimalPool
        '''
        connection = sqlite3.connect(self.file)
        pool = AnimalPoolToolkit()
        pool.loadAnimals(connection)
        pool.loadDetection(start=self.tStartPeriod, end=self.tStopFramePeriod, lightLoad=True)
        connection.close()

        return pool


    def computeActivityPerTimeBin(self):
        self.activity = {}
        self.totalDistance = {}
        self.results = {}

        for animal in self.pool.animalDictionary.keys():
            rfid = self.pool.animalDictionary[animal].RFID
            self.activity[rfid] = self.pool.animalDictionary[animal].getDistancePerBin(binFrameSize=self.timebinInFrame,
                                                                             minFrame=self.tStartPeriod, maxFrame=self.tStopFramePeriod)
            self.totalDistance[rfid] = self.pool.animalDictionary[animal].getDistance(tmin=self.tStartPeriod, tmax=self.tStopFramePeriod)

            nTimeBins = len(self.activity[rfid])
            print(nTimeBins)

            timeLine = [0]
            for t in range(1, nTimeBins):
                x = timeLine[t - 1] + self.timebin
                timeLine.append(x)

            self.results[rfid] = {}
            for time, distance in zip(timeLine, self.activity[rfid]):
                self.results[rfid][time] = distance


        return {'totalDistance': self.totalDistance, 'activity': self.activity, 'results': self.results}


    def getAllResults(self):
        return {'metadata': self.getMetadata(), 'totalDistance': self.totalDistance, 'activity': self.activity, 'results': self.results}


    def organizeResults(self):
        '''
        Organize the results dict in a new dict organizedResults
        reorganizedResults like
        {
            'metadata': experimentMetaData,
            'rfid': {
                'ID': ID,
                'sex': sex,
                'name': name,
                'genotype': genotype,
                'var1': var1,
                ...
                'totalDistance': totalDistance,
                'results': results
            }
        }
        '''
        self.reorganizedResults = {
            'metadata': self.getMetadata(),
        }

        for rfid in self.results:
            self.reorganizedResults[rfid] = {
                'totalDistance': self.totalDistance[rfid],
                'results': self.results[rfid]
            }
            for key, value in self.animals[rfid].items():
                self.reorganizedResults[rfid][key] = value



    def exportReorganizedResultsToJsonFile(self, nameFile="activityResults"):
        self.organizeResults()
        jsonFile = json.dumps(self.reorganizedResults, indent=4)
        with open(f"{self.name}_{nameFile}.json", "w") as outputFile:
            outputFile.write(jsonFile)

    def convertFrameNumberForTimeBinTimeline(self, frameNumber):
        # axe en minute depuis le début de période!
        return ((frameNumber - self.tStartPeriod)/self.timebinInFrame)*self.timebin

    def plotNightTimeLine(self):
        connection = sqlite3.connect(self.file)

        nightTimeLineList = []
        nightTimeLine = EventTimeLine(connection, "night")
        nightTimeLineList.append(nightTimeLine)

        connection.close()

        ax = plt.gca()
        for nightEvent in nightTimeLine.getEventList():
            print("Night")
            if nightEvent.startFrame >= self.tStartPeriod and nightEvent.startFrame <= self.tStopFramePeriod:
                print("gna")
                print(self.tStartPeriod)
                print(nightEvent.startFrame)
                print(nightEvent.endFrame)
                if nightEvent.endFrame >= self.tStopFramePeriod:
                    nightEvent.endFrame = self.tStopFramePeriod
                print(f"Start night: {self.convertFrameNumberForTimeBinTimeline(nightEvent.startFrame)}")
                print(f"End night: {self.convertFrameNumberForTimeBinTimeline(nightEvent.endFrame)}")
                ax.axvspan(self.convertFrameNumberForTimeBinTimeline(nightEvent.startFrame), self.convertFrameNumberForTimeBinTimeline(nightEvent.endFrame), alpha=0.1, color='black')
                ax.text(self.convertFrameNumberForTimeBinTimeline(nightEvent.startFrame) + (self.convertFrameNumberForTimeBinTimeline(nightEvent.endFrame) - self.convertFrameNumberForTimeBinTimeline(nightEvent.startFrame)) / 2, 100, "dark phase",
                        fontsize=8, ha='center')

    def plotActivity(self):
        if len(self.results) == 0:
            print("No results")
        else:
            fig, ax = plt.subplots(1, 1, figsize=(8, 2))
            ax = plt.gca()  # get current axis
            ax.set_xlabel("time")

            for animal in self.results:
                print("plot: ")
                print(self.results[animal])
                ax.plot(self.results[animal].keys(), self.results[animal].values(), linewidth=0.6, label=f"{animal}: {round(self.totalDistance[animal])}")
            plt.title(self.name)
            ax.legend(loc="upper center")
            self.plotNightTimeLine()

            plt.show()
            fig.savefig(f"activity_{self.name}.pdf")


class ActivityExperimentPool:
    def __init__(self):
        self.activityExperiments = []
        self.results = {}
        self.mergedResults = {}
        self.reorganizedResultsPerIndividual = {}
        self.reorganizedResults = {}
        self.sexesList = []
        self.genotypeList = []

    def addActivityExperiment(self, experiment):
        self.activityExperiments.append(experiment)

    def addActivityExperimentWithDialog(self, tStartPeriod=0, durationPeriod=24, timebin=10):
        files = getFilesToProcess()
        if (files != None):
            for file in files:
                # create the activity experiment
                print(file)
                experiment = ActivityExperiment(file, tStartPeriod=tStartPeriod, durationPeriod=durationPeriod, timebin=timebin)
                self.addActivityExperiment(experiment)

    def setWholeCageCoordinatesExperimentPool(self, wholeCageCoordinates):
        '''
        :param wholeCageCoordinates: format like {'xa': 168, 'xb': 343, 'ya': 120, 'yb': 296}
        '''
        for experiment in self.activityExperiments:
            experiment.setWholeCageCoordinates(wholeCageCoordinates)


    def computeActivityBatch(self):
        '''
        Compute a batch of activity experiment
        '''
        for experiment in self.activityExperiments:
            self.results[experiment.getName()] = experiment.computeActivityPerTimeBin()
            experiment.exportReorganizedResultsToJsonFile()
            experiment.plotActivity()
        return self.results


    def mergeResults(self):
        '''
        Organize the results of the activity experiment
        '''
        if len(self.activityExperiments) == 0:
            print("There is no experiment yet")
        else:
            for experiment in self.activityExperiments:
                self.mergedResults[experiment.getName()] = experiment.reorganizedResults


    # def exportResultsSortedBy(self, filters: list):
    #     '''
    #     filters: list of filters to sort the results
    #     Return the results sorted by the given filters
    #     '''
    #


    def exportReorganizedResultsToJsonFile(self, nameFile="activityResults"):
        jsonFile = json.dumps(self.reorganizedResults, indent=4)
        with open(f"{nameFile}.json", "w") as outputFile:
            outputFile.write(jsonFile)




def setAnimalType( aType ):
    global animalType
    animalType = aType


### for test
## single experiment
setAnimalType(AnimalType.MOUSE)

# file = r"C:\Users\torquetn\Documents\20200909_test_temp_Experiment 3580.sqlite"
# xp = ActivityExperiment(file, 1, 1, 10)
# dataManip = xp.computeActivityPerTimeBin()

## experiment pool test
experimentPool = ActivityExperimentPool()
experimentPool.addActivityExperimentWithDialog(1, 48, 10)
experimentPool.computeActivityBatch()
# experimentPool.organizeResults()
# experimentPool.exportReorganizedResultsAsTable("nameTableFile")
# experimentPool.exportReorganizedResultsToJsonFile("nameJsonFile")