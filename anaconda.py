#!/usr/bin/env python

import re
import sys
import os.path
import webbrowser

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

# Analyzes an instruction, returns whether this instruction causes leakage or is overwritten
def analyzeInstruction(trackInfo, instruction, trackTree, register):
    result = Result.NOTHING
    
    if instruction.isSink() and trackInfo.trackType() == TrackInfo.SOURCE:
        trackInfo.markAsLeaking()
        trackTree.addComment(instruction, register, '<span style="color:#f00">Data is put in sink!</span>')
        trackTree.setLeakText('Leaks: ')
        return Result.LEAKED
    
    parameterIndices = [idx for idx, param in enumerate(instruction.parameters()) if param == register]
    
    
    for parameterIndex in parameterIndices:
        if parameterIndex == 0 and instruction.type() == InstructionType.INVOKE:
        
            if trackInfo.trackType() == TrackInfo.SINK: # if tracking a sink mark instruction as sink
                instruction.markAsSink()
                trackTree.addComment(instruction, register, 'Marked instruction as sink.')
            else:                           # if tracking a source continue tracking
                # Function is called on a source object. Track the result.
                if instruction.parameters()[-1][-1] == 'V': # it returns a void
                    trackTree.addComment(instruction, register, 'Function ' + str(instruction.parameters()[-1]) + ' called on source object, but returns void')
                else:
                    trackTree.addComment(instruction, register, 'Function ' + str(instruction.parameters()[-1]) + ' called on source object, tracking result')

                    result = startTracking(trackInfo, instruction.nextInstructions(), trackTree)

        elif instruction.type() == InstructionType.INVOKE or instruction.type() == InstructionType.STATICINVOKE:
            # The register is passed as a parameter to a function. Attempt to continue tracking in the function
            # TODO: Return by reference
                    
            # Attempt to find the method used within the apk
            definitions = instruction.classesAndMethodsByStructure(structure)
            note = ''
            
            numberOfDefinitions = 0
            for _, instructionMethod in definitions:
                if not (instructionMethod is None):
                    numberOfDefinitions += 1
                else:
                    # Class is not defined within APK
                    className, methodName = instruction.classAndMethod()
                    note += 'Information is used in method call not defined in apk'

                    if instruction.type() == InstructionType.INVOKE:
                        # It was an instance call, track the object the function was called on

                        result = startTracking(trackInfo, [instruction], trackTree, instruction.parameters()[0])
                        note += ',\ntracking the instance the method is called on'
                        
                    if not instruction.parameters()[-1].endswith(')V'): # It returns something
                        note += '\nTracking the data this call returns'
                        result = startTracking(trackInfo, instruction.nextInstructions(), trackTree)
                    
                    
                    
            if numberOfDefinitions > 0:  
                note += 'Information is used in method call defined in apk,\n' + str(numberOfDefinitions) + ' definitions of the called method have been found:'
            
            for _, instructionMethod in definitions:
                if not (instructionMethod is None):
                    # Class defined in the APK, continue tracking
                    if not instructionMethod.hasCode():
                        note += '\nNo code was found for method ' + instruction.method().memberOf().name() + ' ' + instruction.method().name()
                        continue
                
                    note += '<span style="color:#f00">\nTracking method ' + instructionMethod.memberOf().name() + ' ' + instructionMethod.name() + '</span>'

                    parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)

                    result = startTracking(trackInfo, [instructionMethod.firstInstruction()], trackTree, parameterRegister)
    
            # Finally add note as comment
            trackTree.addComment(instruction, register, note)
                
        elif instruction.type() == InstructionType.IF:
            # The register is used in a if statement
            trackTree.addComment(instruction, register, 'Data is used in if statement')
            
        elif instruction.type() == InstructionType.FIELDPUT:
            # The content of the register is put inside a field, either of an instance or a class. Use trackFieldUsages to
            # lookup where this field is read and continue tracking there
            parameters = instruction.parameters()
            trackTree.addComment(instruction, register, '<span style="color:#f00">Data is put in field ' + str(parameters[-2]) + ' of class ' + str(parameters[-3]) + '\nSearching for usages</span>')

            result = trackFieldUsages(trackInfo, parameters[-3], parameters[-2], parameters[-1], trackTree)
            
        elif instruction.type() == InstructionType.ARRAYPUT:
            if parameterIndex == 0: # Data is put in an array. Track the array
                trackTree.addComment(instruction, register, 'Data is put in an array, tracking array')
                newRegister = instruction.parameters()[1] # target array
                result = startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
            else:
                # Something else is put into the array being tracked (param = 1), or it is used as index (param = 2)
                trackTree.addComment(instruction, register, 'Data is put in source array or used as index')
            
        elif instruction.type() == InstructionType.FIELDGET:
            # Register is used in a get instruction. This means either a field of the source object is read, or the
            # register is overwritten. Case is determined by the parameter index.
            if parameterIndex == 0:
                trackTree.addComment(instruction, register, 'Register was overwritten')
                result = Result.OVERWRITTEN
                continue
            else:
                trackTree.addComment(instruction, register, 'Data was read from source object, tracking read data')

                newRegister = instruction.parameters()[0] # target register
                result = startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
                
        elif instruction.type() == InstructionType.STATICGET:
            # Register is used in a static get, the register is overwritten.
            trackTree.addComment(instruction, register, 'Register was overwritten')
            result = Result.OVERWRITTEN
            continue
            
        elif instruction.type() == InstructionType.ARRAYGET:
            if parameterIndex == 0:
                # Data is put into the tracked register, the register is overwritten
                trackTree.addComment(instruction, register, 'Register was overwritten')
                result = Result.OVERWRITTEN
                continue
            elif parameterIndex == 1:
                # Data is taken out of tainted Array, assume this data is tainted as well
                trackTree.addComment(instruction, register, 'Data read from tainted array')
                newRegister = instruction.parameters()[0] # target register
                result = startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
            elif parameterIndex == 2:
                trackTree.addComment(instruction, register, 'Tainted data used as index for array')
            
        elif instruction.type() == InstructionType.RETURN:
            # Register is used in return instruction. Use trackMethodUsages to look for usages of this function and track
            # the register containing the result.
            
            trackTree.addComment(instruction, register, '<span style="color:#f00">Data was returned. Looking for usages of this function</span>')
            result = trackMethodUsages(trackInfo, instruction.method().memberOf().name(), instruction.method().name(), trackTree)
            
        elif instruction.type() == InstructionType.MOVE:
            # Value is moved into other register. When first parameter the register is overwritten, else the value is
            # copied into another register. Track that register as well.
            
            if parameterIndex == 0:
                trackTree.addComment(instruction, register, 'Register was overwritten')
                result = Result.OVERWRITTEN
                continue
            else:
                newRegister = instruction.parameters()[0]
                trackTree.addComment(instruction, register, 'Data copied into new register ' + newRegister)
                result = startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
        
        elif instruction.type() == InstructionType.CONVERSION or instruction.type() == InstructionType.OPERATION:
            # For both a conversion or operation instruction, the result is put in the register which is parameter 0.
            # If the tracked register is used as second or third parameter, the taint should propegate to the target
            # register, parameter 0.
            if parameterIndex == 0:
                trackTree.addComment(instruction, register, 'Register was overwritten')
                result = Result.OVERWRITTEN
                continue
            else: # Tracked data is converted
                trackTree.addComment(instruction, register, 'Data converted into different type or used in operation, tracking result')
                newRegister = instruction.parameters()[0]
                result = startTracking(trackInfo, instruction.nextInstructions(), trackTree, newRegister)
        elif instruction.type() == InstructionType.INSTANCEOF or instruction.type() == InstructionType.ARRAYLENGTH:
            if parameterIndex == 0:
                trackTree.addComment(instruction, register, 'Register was overwritten')
                result = Result.OVERWRITTEN
                continue
        elif instruction.type() == InstructionType.CONST or instruction.type() == InstructionType.NEWINSTANCE or \
             (instruction.type() == InstructionType.NEWARRAY and parameterIndex == 0):
            # Value is put in tracked register, register overwritten

            trackTree.addComment(instruction, register, 'Register was overwritten')
            result = Result.OVERWRITTEN
            continue  
        else:
            # Uncaught instruction used
            trackTree.addComment(instruction, register, 'Unknown operation performed')
    
    return result

# Call this when you want to track some new register, returns whether any of the instructions causes leakage
def startTracking(trackInfo, instructions, trackTree, register = None):
    return distribute(trackInfo, [None] + instructions, {}, trackTree, register)

# Distribute the given list of instructions over several tracks
def distribute(trackInfo, instructions, visitedInstructions, trackTree, register):
    if instructions == []:
        return None, Result.NOTHING
        
    result = Result.NOTHING
    if len(instructions) > 1:
        for instruction in instructions[1:]:
            if trackFromCall(trackInfo, instruction, visitedInstructions, trackTree, register) == Result.LEAKED:
                result = Result.LEAKED
   
    return instructions[0], result

# Track a register from the specified block and instrucion index in the provided method. If no register is provided,
# attempt to read the register to track from the move-result instruction on the instruction specified.
def trackFromCall(trackInfo, instruction, visitedInstructions, trackTree, register):   
    pathHistory = history.get((instruction, register), None)
    
    if not (pathHistory is None):
        trackMessage = 'Stopping: Tracked this before'
        if pathHistory.leaks():
            trackMessage += ', known to leak'       
            trackInfo.markAsLeaking()
            if not (trackTree is None):
                trackTree.setLeakText('Branch leaks: ')
        
        #if not (trackTree is None):
        #    trackTree.addChild(Tree(trackTree, [instruction, trackMessage]))
        return Result.LEAKED
    
    pathHistory = PathInfo()
    history[(instruction, register)] = pathHistory
         
    # This is needed for comments
    previousHandledInstruction = instruction 
    endResult = Result.NOTHING
       
    # Check if a register was provided. If not, retrieve the register to track from move-result in startInstruction 
    if register is None:
        if instruction.type() == InstructionType.MOVERESULT:
            register = instruction.parameters()[0]
            
            instruction, endResult = distribute(trackInfo, instruction.nextInstructions(), visitedInstructions, trackTree, register)
            if instruction is None:
                return endResult # end of the method
        else:
            return endResult

    # Have we tracked this register before?
    identifier = [instruction, register]
        
    # Is the method we are currently in the same as the one we were in before?
    inNewMethod = False
    if trackTree is None:
        inNewMethod = True
    else:
        inNewMethod = trackTree.content()[0].method() != instruction.method()
        
    # Tree creation
    if trackTree is None or inNewMethod:
        node = Tree(trackTree, identifier) # If trackTree = None it means this will be the root node
        
        if not (trackTree is None):
            trackTree.addChild(node)
    else: # trackTree is not None and the previous method is the same
        node = trackTree
    
        
    # Print class and method and register we're at    
    #print '>', instruction.method().memberOf().name(), instruction.method().name()
    #print 'Tracking the result in register', register
    
    if visitedInstructions == {}:
        message = 'Tracking register'
        if inNewMethod:
            message += ' (first register tracked in this method)'
        
        if instruction == instruction.method().firstInstruction():
            node.addComment(None, '++' + register, message)
        else:
            node.addComment(previousHandledInstruction, '++' + register, message)
    
    # Iterate over the instructions of this method
    while not (instruction is None):

        # Have we been here before?
        if visitedInstructions.get((instruction, register), False) == True:
            break
    
        visitedInstructions[(instruction, register)] = True
        
        # Only do something if the register is used
        if register in instruction.parameters():
        
            # TODO: maybe add stuff like new-instance
            if instruction.type() == InstructionType.MOVERESULT:
                node.addComment(instruction, '--' + register, 'Stop tracking register')
                break # register is overwritten
            
            result = analyzeInstruction(trackInfo, instruction, node, register)
    
            if result == Result.OVERWRITTEN:
                node.addComment(instruction, '--' + register, 'Stop tracking register')
                break # register is overwritten
            elif result == Result.LEAKED:
                endResult = Result.LEAKED
                
        
        instructions = instruction.nextInstructions()
        instruction, result = distribute(trackInfo, instructions, visitedInstructions, node, register)
        if result == Result.LEAKED:
            endResult = Result.LEAKED
    
    if endResult == Result.LEAKED:
        pathHistory.markAsLeaking()
        if not (trackTree is None):
            node.setLeakText('Branch leaks: ')
    
    if trackTree is None:
        trackedTrees.append((node, trackInfo))
        
    return endResult
    
def trackMethodUsages(trackInfo, className, methodName, trackTree):
    methods = structure.calledMethodsByMethodName(className, methodName)
    #print 'Method', methodName, className 
    #if len(methods): 
    #    print '---------------------------------------------------'
    #    print 'Method', methodName, className, 'is used in', len(methods), 'method(s):\n' 
    

    
    # search through all the methods where it is called
    for method in methods:
        
        instructions = method.calledInstructionsByMethodName(className, methodName)
        for instruction in instructions:
            # Check if this is the first time it's called
            trackInfoParameter = trackInfo
            if trackInfo is None:
                trackInfoParameter = TrackInfo(TrackInfo.SOURCE, className + '->' + methodName + ' is called')
                
            startTracking(trackInfoParameter, instruction.nextInstructions(), trackTree) 

def trackFieldUsages(trackInfo, className, fieldName, type, trackTree):
    methods = structure.calledMethodsByFieldName(className, fieldName, type)
    if methods is None:
        return
    
    #if len(methods): 
    #    print '---------------------------------------------------'
    #    print 'Field', fieldName, className, 'is used in', len(methods), 'method(s):\n' 
        
        
    for method in methods:
        instructions = method.calledInstructionsByFieldName(className, fieldName)
        for instruction in instructions:
            register = instruction.parameters()[0]
            # Check if this is the first time it's called
            trackInfoParameter = trackInfo
            if trackInfo is None:
                trackInfoParameter = TrackInfo(TrackInfo.SOURCE, className + '->' + fieldName + ' is used')
            
            startTracking(trackInfoParameter, instruction.nextInstructions(), trackTree, register)

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
                    #print '---------------------------------------------------'
                    #print 'Listener', superClassName, listener[0], 'is overriden by', subClass.name(), '\n' 
                    parameterNumber = method.numberOfLocalRegisters() + int(listener[1]) + 1
                    startTracking(TrackInfo(TrackInfo.SOURCE, superClassName + '->' + listener[0] + ' overriden'), [method.firstInstruction()], None, 'v' + str(parameterNumber))

def trackSinkUsages(className, methodName, isSink, direct):
    #if direct == 'indirect':
    #    return

    methods = structure.calledMethodsByMethodName(className, methodName)
    
    for method in methods:
        #print 'New', className, 'created in', method.name()
        instructions = method.calledInstructionsByMethodName(className, methodName)
        # Track it and mark new sinks
        for instruction in instructions:
            if 'is-sink' in isSink:
                startTracking(TrackInfo(TrackInfo.SINK, className + ' created'), [instruction], None, instruction.parameters()[0])
            else:
                startTracking(TrackInfo(TrackInfo.SINK, className + ' created'), instruction.nextInstructions(), None)
                

def main():
    optParser = OptionParser(usage='Usage: %prog [options] -f FILENAME')
    optParser.add_option('-f', '--file', action='store', type='string',
            dest='filename', help='the filename of the APK to analyze', default=None)
    optParser.add_option('-b', '--browser', action='store_true', dest='showBrowser',
                         help='open the resulting HTML in your default browser')
    (options, args) = optParser.parse_args()

    if options.filename is None:
        optParser.print_usage()
        print 'A filename is required.'
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
    
    print '****************************'
    print '* Looking for listeners *'
    print '****************************'
    
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
    
    with open('html/results.html', 'w') as htmlFile:
        htmlFile.write(html)
        
    # Crashes under OS X; requires additional resting.
    if options.showBrowser:
        webbrowser.open('html/results.html')

if __name__ == "__main__":
    main()
    

