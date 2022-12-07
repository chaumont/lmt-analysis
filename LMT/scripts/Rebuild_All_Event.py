'''
Created on 13 sept. 2017

@author: Fab
'''

import sqlite3
from lmtanalysis.Animal import *
import matplotlib.pyplot as plt
from lmtanalysis.Event import *
from lmtanalysis.Measure import *

from lmtanalysis.Util import getAllEvents

from lmtanalysis import BuildEventOtherContact, BuildEventPassiveAnogenitalSniff, BuildEventHuddling, BuildEventTrain3, BuildEventTrain4, BuildEventTrain2, BuildEventFollowZone, BuildEventRear5, BuildEventCenterPeripheryLocation, BuildEventRearCenterPeriphery, BuildEventFloorSniffing, BuildEventSocialApproach, BuildEventSocialEscape, BuildEventApproachContact,BuildEventOralOralContact, BuildEventApproachRear, BuildEventGroup2, BuildEventGroup3, BuildEventGroup4, BuildEventOralGenitalContact, BuildEventStop, BuildEventWaterPoint, BuildEventMove, BuildEventGroup3MakeBreak, BuildEventGroup4MakeBreak, BuildEventSideBySide, BuildEventSideBySideOpposite, BuildEventDetection, BuildDataBaseIndex,  BuildEventSAP, BuildEventOralSideSequence, CheckWrongAnimal, CorrectDetectionIntegrity, BuildEventNest4, BuildEventNest3, BuildEventGetAway


from psutil import virtual_memory

from tkinter.filedialog import askopenfilename
from lmtanalysis.TaskLogger import TaskLogger
import sys
import traceback
from lmtanalysis.FileUtil import getFilesToProcess
from lmtanalysis.EventTimeLineCache import flushEventTimeLineCache,\
    disableEventTimeLineCache


from lmtanalysis.EventTimeLineCache import EventTimeLineCached





USE_CACHE_LOAD_DETECTION_CACHE = True

class FileProcessException(Exception):
    pass






def flushEvents( connection, listOfEvents ):

    print("Flushing events...")

    for ev in listOfEvents:

        chrono = Chronometer( "Flushing event " + str(ev) )
        ev.flush( connection );
        chrono.printTimeInS()


def processTimeWindow( connection, file, currentMinT , currentMaxT, listOfEvents, localAnimalType ):

    CheckWrongAnimal.check( connection, tmin=currentMinT, tmax=currentMaxT )

    # Warning: enabling this process (CorrectDetectionIntegrity) will alter the database permanently
    # CorrectDetectionIntegrity.correct( connection, tmin=0, tmax=maxT )

    # BuildEventDetection.reBuildEvent( connection, file, tmin=currentMinT, tmax=currentMaxT )

    animalPool = None

    flushEventTimeLineCache()

    if ( USE_CACHE_LOAD_DETECTION_CACHE ):
        print("Caching load of animal detection...")
        animalPool = AnimalPool( )
        animalPool.loadAnimals( connection )
        animalPool.loadDetection( start = currentMinT, end = currentMaxT )
        for animal in animalPool.getAnimalList():
            animal.setAnimalType( localAnimalType)
        print('animal type: ', animal.animalType)
        print("Caching load of animal detection done.")

    for ev in listOfEvents:

        chrono = Chronometer( str( ev ) )
        ev.reBuildEvent( connection, file, tmin=currentMinT, tmax=currentMaxT, pool = animalPool )
        chrono.printTimeInS()



def process( file, listOfEvents, localAnimalType, minT, maxT, windowT ):

    print(file)

    mem = virtual_memory()
    availableMemoryGB = mem.total / 1000000000
    print( "Total memory on computer: (GB)", availableMemoryGB )

    if availableMemoryGB < 10:
        print( "Not enough memory to use cache load of events.")
        disableEventTimeLineCache()


    chronoFullFile = Chronometer("File " + file )

    connection = sqlite3.connect( file )

    # update missing fields
    try:
        connection = sqlite3.connect( file )
        c = connection.cursor()
        query = "ALTER TABLE EVENT ADD METADATA TEXT";
        c.execute( query )
        connection.commit()

    except:
        print( "METADATA field already exists" , file )

    BuildDataBaseIndex.buildDataBaseIndex( connection, force=False )
    # build sensor data
    animalPool = AnimalPool( )
    animalPool.loadAnimals( connection )
    #animalPool.buildSensorData(file)
    

    currentT = minT

    try:

        flushEvents( connection, listOfEvents )

        while currentT < maxT:

            currentMinT = currentT
            currentMaxT = currentT+ windowT
            if ( currentMaxT > maxT ):
                currentMaxT = maxT

            chronoTimeWindowFile = Chronometer("File "+ file+ " currentMinT: "+ str(currentMinT)+ " currentMaxT: " + str(currentMaxT) );
            processTimeWindow( connection, file, currentMinT, currentMaxT , listOfEvents, localAnimalType)
            chronoTimeWindowFile.printTimeInS()

            currentT += windowT



        print("Full file process time: ")
        chronoFullFile.printTimeInS()


        TEST_WINDOWING_COMPUTATION = False

        if ( TEST_WINDOWING_COMPUTATION ):

            print("*************")
            print("************* TEST START SECTION")
            print("************* Test if results are the same with or without the windowing.")

            # display and record to a file all events found, checking with rolling idA from None to 4. Save nbEvent and total len

            eventTimeLineList = []

            eventList = getAllEvents( connection )
            file = open("outEvent"+str(windowT)+".txt","w")
            file.write( "Event name\nnb event\ntotal duration" )

            for eventName in eventList:
                for animal in range( 0,5 ):
                        idA = animal
                        if idA == 0:
                            idA = None
                        timeLine = EventTimeLineCached( connection, file, eventName, idA,  minFrame=minT, maxFrame=maxT )
                        eventTimeLineList.append( timeLine )
                        file.write( timeLine.eventNameWithId+"\t"+str(len(timeLine.eventList))+"\t"+str(timeLine.getTotalLength())+"\n" )

            file.close()

            #plotMultipleTimeLine( eventTimeLineList )

            print("************* END TEST")

        flushEventTimeLineCache()

    except:

        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error = ''.join('!! ' + line for line in lines)

        t = TaskLogger( connection )
        t.addLog( error )
        flushEventTimeLineCache()

        print( error, file=sys.stderr )

        raise FileProcessException()



def processAll( listOfEvents, localAnimalType, minT, maxT, windowT ):


    files = getFilesToProcess()

    chronoFullBatch = Chronometer("Full batch" )

    if ( files != None ):

        for file in files:
            try:
                print ( "Processing file" , file )
                process( file, listOfEvents, localAnimalType, minT, maxT, windowT )
            except FileProcessException:
                print ( "STOP PROCESSING FILE " + file , file=sys.stderr  )

    chronoFullBatch.printTimeInS()
    print( "*** ALL JOBS DONE ***")


if __name__ == '__main__':

    print("Code launched.")
    
    ''' minT and maxT to process the analysis (in frame) '''
    minT = 0
    
    #maxT = 5000
    maxT = 2*oneHour
    #maxT = (6+1)*oneHour
    ''' time window to compute the events. '''
    windowT = 1*oneDay
    #windowT = 3*oneDay #int (0.5*oneDay)
    
    eventClassList = [
                #BuildEventHuddling,
                BuildEventDetection,
                BuildEventOralOralContact,
                BuildEventOralGenitalContact,
                BuildEventSideBySide,
                BuildEventSideBySideOpposite,
                BuildEventTrain2,
                BuildEventTrain3,
                BuildEventTrain4,
                BuildEventMove,
                BuildEventFollowZone,
                BuildEventRear5,
                BuildEventCenterPeripheryLocation,
                BuildEventRearCenterPeriphery,
                #BuildEventSocialApproach,
                BuildEventGetAway,
                BuildEventSocialEscape,
                BuildEventApproachRear,
                BuildEventGroup2,
                BuildEventGroup3,
                BuildEventGroup4,
                BuildEventGroup3MakeBreak,
                BuildEventGroup4MakeBreak,
                BuildEventStop,
                BuildEventWaterPoint,
                BuildEventApproachContact,
                #BuildEventWallJump,
                BuildEventSAP,
                BuildEventOralSideSequence,
                BuildEventNest3,
                BuildEventNest4
                   ]

    #eventClassList = [BuildEventPassiveAnogenitalSniff, BuildEventOtherContact, BuildEventExclusiveSideSideNoseAnogenitalContact]
    
    '''eventClassList = [
    
                    BuildEventDetection,
                    BuildEventMove,
                    BuildEventRear5,
                    BuildEventCenterPeripheryLocation,
                    BuildEventRearCenterPeriphery,
                    BuildEventStop,
                    BuildEventWaterPoint,
                    BuildEventWallJump,
                    BuildEventSAP
                       ]'''
    eventClassList = [BuildEventFollowZone2]
    
    
    localAnimalType = AnimalType.MOUSE
    processAll( eventClassList, localAnimalType, minT, maxT, windowT )
    print('Job done.')


