#!/usr/bin/env python

import re
import sys

sys.path.append('androguard')

from androlyze import *
from structure import *
from tools import *
 
class TrackType:
    SINK = 0
    SOURCE = 1
 
# Read the list of api sources       
def sources(filename) :
    file = open(filename)
    
    for line in file: # Throw away the first lines
        if '#methods' in line:
            break
    
    functions = []
    for line in file: # Read the functions
        if '#fields' in line: 
            break
            
        classAndFunction = line.split()[0:2]
        if classAndFunction != []:
            classAndFunction[0] = classAndFunction[0].replace('.', '/')
            classAndFunction[0] = 'L' + classAndFunction[0] + ';'
            functions.append(classAndFunction)
    
    fields = []
    for line in file: # Read the fields
        if '#listeners' in line: 
            break
        
        classAndField = line.split()[0:3]
        if classAndField != []:
            classAndField[0] = classAndField[0].replace('.', '/')
            classAndField[0] = 'L' + classAndField[0] + ';'
            classAndField[2] = classAndField[2].replace('.', '/')
            fields.append(classAndField)
    
    listeners = []
    for line in file: # Read the listeners
        line = line.replace('.', '/')
        classAndRest = line.split(None, 1) # The Class name of the listened to + rest
        if classAndRest != []:
            tuple = classAndRest[1].rpartition(')')
            method = tuple[0] + tuple[1]
            rest = tuple[2].split() # Everything behind addlistener function
            listenerMethods = []
            for idx in range(1, len(rest), 2):
                if idx + 1 < len(rest):
                    listenerMethods.append([rest[idx], rest[idx + 1]])
            
            listeners.append(['L' + classAndRest[0] + ';', method, 'L' + rest[0] + ';', listenerMethods])
    
    return functions, fields, listeners
        
# Read the list of api sinks
def sinks(filename) :
    file = open(filename)

    classes = []
    for line in file:
        classAndFunction = line.split()
        if classAndFunction != []:
            classAndFunction[0] = classAndFunction[0].replace('.', '/')
            classAndFunction[0] = 'L' + classAndFunction[0] + ';'
            classes.append(classAndFunction)

    return classes

# Analyze the provided instruction, perform aditional tracking if needed. If register is overwritten in the 
# instruction, return true

def analyzeInstruction(trackType, method, instruction, register, trackedPath):
    print '---->', instruction.opcode(), instruction.parameters()
    
    if instruction.isSink() and trackType == TrackType.SOURCE:
        print 'Data is put in sink!'
        return
    
    parameterIndex = instruction.parameters().index(register)
    blockIdx, instructionIdx = instruction.indices()
    
    if parameterIndex == 0 and instruction.type() == InstructionType.INVOKE:
    
        if trackType == TrackType.SINK: # if tracking a sink mark instruction as sink
            instruction.markAsSink()
            print 'Marking as sink: ', instruction
            return
        else:                           # if tracking a source continue tracking
            # Function is called on a source object. Track the result.
            if instruction.parameters()[-1][-1] == 'V': # it returns a void
                print 'Function', instruction.parameters()[-1], 'called on source object, but returns void'
            else:
                print 'Function', instruction.parameters()[-1], 'called on source object, tracking result'

                trackFromCall(trackType, method, blockIdx, instructionIdx + 1)

    elif instruction.type() == InstructionType.INVOKE or instruction.type() == InstructionType.STATICINVOKE:
        # The register is passed as a parameter to a function. Attempt to continue tracking in the function
        # TODO: Return by reference
        # TODO: doing instructionIdx + 1 while the function we just met might be a sink
        # TODO: in case of unfindable method: what about what it returns? Might be fixed by fixing above TODO and changing to instructionIdx
                
        # Attempt to find the method used within the apk
        usages = instruction.classesAndMethodsByStructure(structure)
        if len(usages) > 0:  
            print 'Information is used in method call defined in apk'
            print len(usages), 'potentially called method(s) have been found'
        else:
            # Class is not defined within APK
            className, methodName = instruction.classAndMethod()
            print 'Method', methodName, 'not found in class', className
            if instruction.type() == InstructionType.INVOKE:
                # It was an instance call, track the object the function was called on
                print 'Tracking the instance the method is called on'
                trackFromCall(trackType, method, blockIdx, instructionIdx, trackedPath, instruction.parameters()[0])
            else: 
                # It was a static call, track the object that was returned, if any
                if instruction.parameters()[-1].endswith(')V'): # it does not return a void
                    print 'Tracking the object returned'
                    instruction.markAsSink()
                    trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath)
            
        
        for _, instructionMethod in usages:
            
            print 'Tracking recursively.....'
            parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)

            trackFromCall(trackType, instructionMethod, 0, 0, trackedPath, parameterRegister)
                
        if instruction.parameters()[-1][-1] != 'V': # It returns something
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath)
            
            
    elif instruction.type() == InstructionType.IF:
        # The register is used in a if statement
        print 'Register is used in if statement'
    
    elif instruction.type() == InstructionType.FIELDPUT:
        # The content of the register is put inside a field, either of an instance or a class. Use trackFieldUsages to
        # lookup where this field is read and continue tracking there
        parameters = instruction.parameters()
        print 'Data is put in field', parameters[-2], 'of class', parameters[-3]

        trackFieldUsages(trackType, parameters[-3], parameters[-2], parameters[-1], trackedPath)
        
    elif instruction.type() == InstructionType.FIELDGET:
        # Register is used in a get instruction. This means either a field of the source object is read, or the
        # register is overwritten. Case is determined by the parameter index.
        if parameterIndex == 0:
            print 'Register was overwritten'
            return True
        else:
            print 'Data was read from source object'
            
    elif instruction.type() == InstructionType.STATICGET:
        # Register is used in a static get, the register is overwritten.
        print 'Register was overwritten'
        return True
    elif instruction.type() == InstructionType.RETURN:
        # Register is used in return instruction. use trackMethodUsages to look for usages of this function and track
        # the register containing the result.
        
        print 'Data was returned. Looking for usages of this function' 
        
        trackMethodUsages(trackType, method.memberOf().name(), method.name(), trackedPath)
        
    elif instruction.type() == InstructionType.MOVE:
        # Value is moved into other register. When first parameter the register is overwritten, else the value is
        # copied into another register. Track that register as well.
        
        if parameterIndex == 0:
            print 'Register was overwritten'
            return True
        else:
            newRegister = instruction.parameters()[0]
            print 'Data copied into new register', newRegister

            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath, newRegister)
        
    else:
        # Uncaught instruction used
        print 'Unknown operation performed'

    

# Track a register from the specified block and instrucion index in the provided method. If no register is provided,
# attempt to read the register to track from the move-result instruction on the instruction specified.

def trackFromCall(trackType, method, startBlockIdx, startInstructionIdx, trackedPath = [], register = None):
    if startBlockIdx >= len(method.blocks()) or startInstructionIdx >= len(method.blocks()[startBlockIdx].instructions()):
        # Out of list bounds!
        return
        
    # Check if a register was provided. If not, retrieve the register to track from move-result in startInstruction 
    if register is None:
        resultInstruction = method.blocks()[startBlockIdx].instructions()[startInstructionIdx]
        if resultInstruction.type() == InstructionType.MOVERESULT:
            register = resultInstruction.parameters()[0]
            startInstructionIdx += 1 # move the pointer to the instruction after the move-result
        else:
            print 'WARNING: No move-result instruction was found, instead \'', method.blocks()[startBlockIdx].instructions()[startInstructionIdx], '\' was found'
            return
    
    # Have we tracked this register before?
    identifier = [method, startBlockIdx, startInstructionIdx, register]
    if identifier in trackedPath:
        print 'RECURSION: Already tracked this register in this method, aborting'
        print 'identifier', method, startBlockIdx, startInstructionIdx, register
        return
    
    trackedPath = trackedPath + identifier
    
    print '>', method.memberOf().name(), method.name()
    print 'Tracking the result in register', register
    
    firstBlock = method.blocks()[startBlockIdx]
    analyzeBlocks(trackType, method, firstBlock, startInstructionIdx, trackedPath, [], register)
    
    print

def analyzeBlocks(trackType, method, block, startInstructionIdx, trackedPath, trackedBlocks, register):   
    if block.index() in trackedBlocks:
        return  # Recursion, stop tracking
    
    trackedBlocks = trackedBlocks + [block.index()]
    # Inspect all instruction for usage of the register
    for instruction in block.instructions()[startInstructionIdx:]: 
        if register in instruction.parameters():
            
            if instruction.type() == InstructionType.MOVERESULT:
                return # register is overwritten
            
            overwritten = analyzeInstruction(trackType, method, instruction, register, trackedPath)

            if overwritten:
                return # register is overwritten
    
    # Recursively analyzze all next blocks
    for nextBlock in block.nextBlocks():
        analyzeBlocks(trackType, method, nextBlock, 0, trackedPath, trackedBlocks, register)
        
 
    
def trackMethodUsages(trackType, className, methodName, trackedPath = []):
    methods = structure.calledMethodsByMethodName(className, methodName)
    #print 'Method', methodName, className 
    if len(methods): 
        print '---------------------------------------------------'
        print 'Method', methodName, className, 'is used in', len(methods), 'method(s):\n' 
    
    # search through all the methods where it is called
    for method in methods:
        
        indices = method.calledInstructionsByMethodName(className, methodName)
        for blockIdx, instructionIdx in indices:
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath) 

def trackFieldUsages(trackType, className, fieldName, type, trackedPath = []):
    methods = structure.calledMethodsByFieldName(className, fieldName, type)
    if methods is None:
        return
    
    if len(methods): 
        print '---------------------------------------------------'
        print 'Field', fieldName, className, 'is used in', len(methods), 'method(s):\n' 
        
    for method in methods:
        indices = method.calledInstructionsByFieldName(className, fieldName)
        for blockIdx, instructionIdx in indices:
            register = method.blocks()[blockIdx].instructions()[instructionIdx].parameters()[0]

            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath, register)

def trackListenerUsages(superClassName, methods):
    # Find the listeners that have been overriden
    superClass = structure.classByName(superClassName)
    if superClass is None:
        return
        
    # Find the subclasses of the found classes and find their overriden methods
    subClasses = superClass.subClasses()
    for subClass in subClasses:
        for methodName, method in subClass.methods().items():
            for listener in methods:
                if listener[0] in methodName:
                    print '---------------------------------------------------'
                    print 'Listener', superClassName, listener[0], 'is overriden by', subClass.name(), '\n' 
                    parameterNumber = method.numberOfLocalRegisters() + int(listener[1]) + 1
                    trackFromCall(TrackType.SOURCE, method, 0, 0, [], 'v' + str(parameterNumber))

def trackSink(className, methodName, isSink, direct):
    methods = structure.calledMethodsByMethodName(className, methodName)
    
    for method in methods:
        print 'New', className, 'created in', method.name()
        indices = method.calledInstructionsByMethodName(className, methodName)
        # Track it and mark new sinks
        for idx in indices:
            if 'is-sink' in isSink:
                instruction = method.blocks()[idx[0]].instructions()[idx[1]]
                trackFromCall(TrackType.SINK, method, idx[0], idx[1], [], instruction.parameters()[0])
            else:
                trackFromCall(TrackType.SINK, method, idx[0], idx[1] + 1)
                

def main():
    point = time.time()

    classAndFunctions, fields, listeners = sources('api_sources.txt')
    sinkClasses = sinks('api_sinks.txt')
    global structure

    structure = APKstructure('apks/LeakTest7.apk')
    #trackSockets.structure = structure
    
    # search for and mark sinks
    for className, methodName, isSink, direct in sinkClasses:
        trackSink(className, methodName, isSink, direct)

    print
    
    # search for all data receiving listeners
    for _, _, superClassName, methods in listeners:
        trackListenerUsages(superClassName, methods)

    print
    
    global trackedMethods
    trackedMethods = []
    # search for all tainted methods
    for className, methodName in classAndFunctions:
        trackMethodUsages(TrackType.SOURCE, className, methodName)
        
    for className, fieldName, type in fields:
        trackFieldUsages(TrackType.SOURCE, className, fieldName, type)
    

    print 'total time: ', time.time() - point 

if __name__=="__main__":
    main()
    


#get_name: type of instruction
#get_output: argument to instruction
#get_literals: variables

