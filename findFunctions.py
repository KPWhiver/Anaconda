#!/usr/bin/env python

import re
import sys
import os.path

sys.path.append('androguard')

from androlyze import *
from structure import *
from tools import *
from tree import *
from jinja2 import Template
from optparse import OptionParser
 
class TrackInfo:
    SINK = 0
    SOURCE = 1
    
    def __init__(self, trackType, reason):
        self.d_trackType = trackType
        self.d_reason = reason
        self.d_leaks = False
        
    def trackType(self):
        return self.d_trackType
    
    def reason(self):
        return self.d_reason
    
    def markAsLeaking(self):
        self.d_leaks = True
        
    def leaks(self):
        return self.d_leaks
        
class PathInfo:
    def __init__(self):
        self.d_leaks = False
        
    def markAsLeaking(self):
        self.d_leaks = True
        
    def leaks(self):
        return self.d_leaks
 
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

class Result:
    OVERWRITTEN = 0
    LEAKED = 1
    NOTHING = 2

def analyzeInstruction(trackInfo, instruction, trackTree, register):
    print '---->', instruction.opcode(), instruction.parameters()
    
    result = Result.NOTHING
    
    if instruction.isSink() and trackInfo.trackType() == TrackInfo.SOURCE:
        trackInfo.markAsLeaking()
        print 'Data is put in sink!'
        trackTree.addComment(instruction, 'Data is put in sink!')
        return Result.LEAKED
    
    parameterIndices = [idx for idx, param in enumerate(instruction.parameters()) if param == register]
    
    
    for parameterIndex in parameterIndices:
        if parameterIndex == 0 and instruction.type() == InstructionType.INVOKE:
        
            if trackInfo.trackType() == TrackInfo.SINK: # if tracking a sink mark instruction as sink
                instruction.markAsSink()
                print 'Marking as sink: ', instruction
                trackTree.addComment(instruction, 'Marked instruction as sink.')
                return result
            else:                           # if tracking a source continue tracking
                # Function is called on a source object. Track the result.
                if instruction.parameters()[-1][-1] == 'V': # it returns a void
                    print 'Function', instruction.parameters()[-1], 'called on source object, but returns void'
                    trackTree.addComment(instruction, 'Function ' + str(instruction.parameters()[-1]) + ' called on source object, but returns void')
                else:
                    print 'Function', instruction.parameters()[-1], 'called on source object, tracking result'
                    trackTree.addComment(instruction, 'Function ' + str(instruction.parameters()[-1]) + ' called on source object, tracking result')

                    startTracking(trackInfo, instruction.nextInstructions(), trackTree)

        elif instruction.type() == InstructionType.INVOKE or instruction.type() == InstructionType.STATICINVOKE:
            # The register is passed as a parameter to a function. Attempt to continue tracking in the function
            # TODO: Return by reference
            # TODO: doing instructionIdx + 1 while the function we just met might be a sink
            # TODO: in case of unfindable method: what about what it returns? Might be fixed by fixing above TODO and changing to instructionIdx
                    
            # Attempt to find the method used within the apk
            definitions = instruction.classesAndMethodsByStructure(structure)
            if len(definitions) > 0:  
                print 'Information is used in method call defined in apk'
                print len(definitions), 'definitions of the called method have been found'
                trackTree.addComment(instruction, 'Information is used in method call defined in apk')
                trackTree.addComment(instruction, str(len(definitions)) + ' definitions of the called method have been found')
            else:
                # Class is not defined within APK
                className, methodName = instruction.classAndMethod()
                print 'Method', methodName, 'not found in class', className
                trackTree.addComment(instruction, 'Method ' + str(methodName) + ' not found in class ' + str(className))

                if instruction.type() == InstructionType.INVOKE:
                    # It was an instance call, track the object the function was called on
                    print 'Tracking the instance the method is called on'

                    startTracking(trackInfo, [instruction], trackTree, instruction.parameters()[0])
                    trackTree.addComment(instruction, 'Tracking the instance the method is called on')
                
            # Defined within the apk, continue tracking the data in the method definition
            for _, instructionMethod in definitions:
                if not instructionMethod.hasCode():
                    print 'No code was found for method', instruction.method().memberOf().name(), instruction.method().name()
                    continue
                
                print 'Tracking recursively.....'
                trackTree.addComment(instruction, 'Tracking recursively...')

                parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)

                startTracking(trackInfo, [instructionMethod.firstInstruction()], trackTree, parameterRegister)
            
            # Check if something was returned, track the register it was put in
            if not instruction.parameters()[-1].endswith(')V'): # It returns something
                print 'Tracking the object returned'

                trackTree.addComment(instruction, 'Tracking the object returned')
                instruction.markAsSink()
                startTracking(trackInfo, instruction.nextInstructions(), trackTree)
                
                
        elif instruction.type() == InstructionType.IF:
            # The register is used in a if statement
            print 'Register is used in if statement'
            trackTree.addComment(instruction, 'Register is used in if statement')
            
        elif instruction.type() == InstructionType.FIELDPUT:
            # The content of the register is put inside a field, either of an instance or a class. Use trackFieldUsages to
            # lookup where this field is read and continue tracking there
            parameters = instruction.parameters()
            print 'Data is put in field', parameters[-2], 'of class', parameters[-3]
            trackTree.addComment(instruction, 'Data is put in field ' + str(parameters[-2]) + ' of class ' + str(parameters[-3]))

            trackFieldUsages(trackInfo, parameters[-3], parameters[-2], parameters[-1], trackTree)
            
        elif instruction.type() == InstructionType.ARRAYPUT:
            if parameterIndex == 0: # Data is put in an array. Track the array
                print "Data is put in an array"
                newRegister = instruction.parameters()[1] # target array
                startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
            else:
                # Something else is put into the array being tracked (param = 1), or it is used as index (param = 2)
                print "Data is put in source array or used as index"
            
        elif instruction.type() == InstructionType.FIELDGET:
            # Register is used in a get instruction. This means either a field of the source object is read, or the
            # register is overwritten. Case is determined by the parameter index.
            if parameterIndex == 0:
                print 'Register was overwritten'
                result = Result.OVERWRITTEN
                continue
            else:
                print 'Data was read from source object'
                
        elif instruction.type() == InstructionType.STATICGET:
            # Register is used in a static get, the register is overwritten.
            print 'Register was overwritten'
            result = Result.OVERWRITTEN
            continue
            
        elif instruction.type() == InstructionType.ARRAYGET:
            if parameterIndex == 0:
                # Data is put into the tracked register, the register is overwritten
                print 'Register was overwritten'
                result = Result.OVERWRITTEN
                continue
            elif parameterIndex == 1:
                # Data is taken out of tainted Array, assume this data is tainted as well
                print 'Data read from tainted array'
                newRegister = instruction.parameters()[0] # target register
                startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
            elif parameterIndex == 2:
                print 'Tainted data used as index for array'
            
        elif instruction.type() == InstructionType.RETURN:
            # Register is used in return instruction. Use trackMethodUsages to look for usages of this function and track
            # the register containing the result.
            
            print 'Data was returned. Looking for usages of this function' 
            
            trackMethodUsages(trackInfo, instruction.method().memberOf().name(), instruction.method().name(), trackTree)
            
        elif instruction.type() == InstructionType.MOVE:
            # Value is moved into other register. When first parameter the register is overwritten, else the value is
            # copied into another register. Track that register as well.
            
            if parameterIndex == 0:
                print 'Register was overwritten'
                result = Result.OVERWRITTEN
                continue
            else:
                newRegister = instruction.parameters()[0]
                print 'Data copied into new register', newRegister

                startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
        
        elif instruction.type() == InstructionType.CONVERSION or instruction.type() == InstructionType.OPERATION:
            # For both a conversion or operation instruction, the result is put in the register which is parameter 0.
            # If the tracked register is used as second or third parameter, the taint should propegate to the target
            # register, parameter 0.
            if parameterIndex == 0:
                print 'Register was overwritten'
                result = Result.OVERWRITTEN
                continue
            else: # Tracked data is converted
                print 'Data converted into different type or used in operation'
                newRegister = instruction.parameters()[0]
                startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
        elif instruction.type() == InstructionType.INSTANCEOF or instruction.type() == InstructionType.ARRAYLENGTH:
            if parameterIndex == 0:
                print 'Register was overwritten'
                result = Result.OVERWRITTEN
                continue
        elif instruction.type() == InstructionType.CONST or instruction.type() == InstructionType.NEWINSTANCE or \
             (instruction.type() == InstructionType.NEWARRAY and parameterIndex == 0):
            # Value is put in tracked register, register overwritten

            print 'Register was overwritten'
            result = Result.OVERWRITTEN
            continue  
        else:
            # Uncaught instruction used
            # TODO: new-instance
            print 'Unknown operation performed'
    
    return result

# Call this when you want to track some new register
def startTracking(trackInfo, instructions, trackTree, register = None):
    distribute(trackInfo, [None] + instructions, {}, trackTree, register)

# Distribute the given list of instructions over several tracks
def distribute(trackInfo, instructions, visitedInstructions, trackTree, register):
    if instructions == []:
        print "No next instruction was found"
        return None
    if len(instructions) > 1:
        for instruction in instructions[1:]:
            trackFromCall(trackInfo, instruction, visitedInstructions, trackTree, register)
   
    return instructions[0]

# Track a register from the specified block and instrucion index in the provided method. If no register is provided,
# attempt to read the register to track from the move-result instruction on the instruction specified.
def trackFromCall(trackInfo, instruction, visitedInstructions, trackTree, register):   
    pathHistory = history.get((instruction, register), None)
    
    if not (pathHistory is None):
        if pathHistory.leaks():
            print 'LEAK LEAK LEAK'
            trackInfo.markAsLeaking()
        
        print 'ALREADY TRACKED: Already tracked this method from this starting point, aborting'
        print 'method: ', instruction.method()
        print '    instruction:', instruction, ', with register:', register
        return
    
    pathHistory = PathInfo()
    history[(instruction, register)] = pathHistory
         
    # Check if a register was provided. If not, retrieve the register to track from move-result in startInstruction 
    if register is None:
        if instruction.type() == InstructionType.MOVERESULT:
            register = instruction.parameters()[0]
            instruction = distribute(trackInfo, instruction.nextInstructions(), visitedInstructions, trackTree, register)
            if instruction is None:
                return # end of the method
        else:
            print 'WARNING: No move-result instruction was found, instead \'', instruction, '\' was found'
            return

    # Have we tracked this register before?
    identifier = [instruction, register]
    
    """
    # Tree creation
    node = Tree(trackTree, identifier) # If trackTree = None it means this will be the root node
    if not (trackTree is None):
        trackTree.addChild(node)
    """
    
    # Tree creation
    if trackTree is None or trackTree.content()[0].method() != instruction.method():
        node = Tree(trackTree, identifier) # If trackTree = None it means this will be the root node
        
        if not (trackTree is None):
            trackTree.addChild(node)
    else: # trackTree is not None and the previous method is the same
        node = trackTree
    
        
    # Print class and method and register we're at    
    print '>', instruction.method().memberOf().name(), instruction.method().name()
    print 'Tracking the result in register', register
    
    # Iterate over the instructions of this method
    while not (instruction is None):

        # Have we been here before?
        if visitedInstructions.get((instruction, register), False) == True:
            print 'LOOPING: Already tracked this location in this method, aborting'
            print instruction, register
            break
    
        visitedInstructions[(instruction, register)] = True
        
        # Only do something if the register is used
        if register in instruction.parameters():
        
            # TODO: maybe add stuff like new-instance
            if instruction.type() == InstructionType.MOVERESULT:
                break # register is overwritten
            
            result = analyzeInstruction(trackInfo, instruction, node, register)
    
            if result == Result.OVERWRITTEN:
                break # register is overwritten
            elif result == Result.LEAKED:
                pathHistory.markAsLeaking()
        
        instructions = instruction.nextInstructions()
        instruction = distribute(trackInfo, instructions, visitedInstructions, node, register)
    
    print
    if trackTree is None:
        trackedTrees.append((node, trackInfo)) #node.toHTML()#toString()
        print '<------>', trackInfo.reason()
    
def trackMethodUsages(trackInfo, className, methodName, trackTree):
    methods = structure.calledMethodsByMethodName(className, methodName)
    #print 'Method', methodName, className 
    if len(methods): 
        print '---------------------------------------------------'
        print 'Method', methodName, className, 'is used in', len(methods), 'method(s):\n' 
    
    # Check if this is the first time it's called
    if trackInfo is None:
        trackInfo = TrackInfo(TrackInfo.SOURCE, className + '->' + methodName + ' is called')
    
    # search through all the methods where it is called
    for method in methods:
        
        instructions = method.calledInstructionsByMethodName(className, methodName)
        for instruction in instructions:
            
            startTracking(trackInfo, instruction.nextInstructions(), trackTree) 

def trackFieldUsages(trackInfo, className, fieldName, type, trackTree):
    methods = structure.calledMethodsByFieldName(className, fieldName, type)
    if methods is None:
        return
    
    if len(methods): 
        print '---------------------------------------------------'
        print 'Field', fieldName, className, 'is used in', len(methods), 'method(s):\n' 
        
    # Check if this is the first time it's called
    if trackInfo is None:
        trackInfo = TrackInfo(TrackInfo.SOURCE, className + '->' + fieldName + ' is used')
        
    for method in methods:
        instructions = method.calledInstructionsByFieldName(className, fieldName)
        for instruction in instructions:
            register = instruction.parameters()[0]

            
            startTracking(trackInfo, instruction.nextInstructions(), trackTree, register)

def trackListenerUsages(superClassName, methods):
    # Find the listeners that have been overriden
    superClass = structure.classByName(superClassName)
    if superClass is None:
        return
        
    # Find the subclasses of the found classes and find their overriden methods
    subClasses = superClass.subClasses()
    for subClass in subClasses:
        # Check if any of the methods in the subclass match a listener method
        for methodName, method in subClass.methods().items():
            for listener in methods:
                if listener[0] in methodName:
                    print '---------------------------------------------------'
                    print 'Listener', superClassName, listener[0], 'is overriden by', subClass.name(), '\n' 
                    parameterNumber = method.numberOfLocalRegisters() + int(listener[1]) + 1
                    startTracking(TrackInfo(TrackInfo.SOURCE, superClassName + '->' + listener[0] + ' overriden'), [method.firstInstruction()], None, 'v' + str(parameterNumber))

def trackSinkUsages(className, methodName, isSink, direct):
    if direct == 'indirect':
        return

    methods = structure.calledMethodsByMethodName(className, methodName)
    
    for method in methods:
        print 'New', className, 'created in', method.name()
        instructions = method.calledInstructionsByMethodName(className, methodName)
        # Track it and mark new sinks
        for instruction in instructions:
            if 'is-sink' in isSink:
                startTracking(TrackInfo(TrackInfo.SINK, className + ' created'), [instruction], None, instruction.parameters()[0])
            else:
                startTracking(TrackInfo(TrackInfo.SINK, className + ' created'), instruction.nextInstructions(), None)
                

def main():
    optParser = OptionParser(usage='Usage: %prog [options] -f FILENAME')
    optParser.add_option("-f", "--file", action="store", type="string",
            dest="filename", help="the filename of the APK to analyze", default=None)
    (options, args) = optParser.parse_args()

    if options.filename is None:
        optParser.print_usage()
        print "A filename is required."
        return

    if not os.path.isfile(options.filename):
        print 'File "' + options.filename + '" doesn\'t exist.'
        return


    point = time.time()

    classAndFunctions, fields, listeners = sources('api_sources.txt')
    sinkClasses = sinks('api_sinks.txt')
    global structure
    global trackedTrees
    global history
    trackedTrees = []
    history = {}
    
    structure = APKstructure(options.filename)
    
    # search for and mark sinks
    print '*****************'
    print '* Marking sinks *'
    print '*****************'
    for className, methodName, isSink, direct in sinkClasses:
        trackSinkUsages(className, methodName, isSink, direct)

    print
    
    # search for all data receiving listeners
    for _, _, superClassName, methods in listeners:
        trackListenerUsages(superClassName, methods)

    print
    
    # search for all tainted methods

    print '****************************'
    print '* Tracking tainted methods *'
    print '****************************'
    for className, methodName in classAndFunctions:
        trackMethodUsages(None, className, methodName, None)
        
    for className, fieldName, type in fields:
        trackFieldUsages(None, className, fieldName, type, None)
    

    print 'total time: ', time.time() - point 
    
    # make html page
    with open('html/results.text', 'r') as textFile:
        text = textFile.read()
        
    template = Template(text)
    html = template.render(treeStructure = trackedTrees)
    
    with open("html/results.html", "w") as htmlFile:
        htmlFile.write(html)

if __name__ == "__main__":
    main()
    

