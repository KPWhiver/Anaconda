#!/usr/bin/env python

import re
import sys

sys.path.append('androguard')

from androlyze import *
from structure import *
from tools import *
from tree import *
from jinja2 import Template
 
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

def analyzeInstruction(trackType, method, instruction, register, trackTree):
    print '---->', instruction.opcode(), instruction.parameters()
    
    if instruction.isSink() and trackType == TrackType.SOURCE:
        print 'Data is put in sink!'
        blockIdx, instructionIdx = instruction.indices()
        trackTree.addComment(blockIdx, instructionIdx, 'Data is put in sink!')
        return
    
    parameterIndex = instruction.parameters().index(register)
    blockIdx, instructionIdx = instruction.indices()
    
    if parameterIndex == 0 and instruction.type() == InstructionType.INVOKE:
    
        if trackType == TrackType.SINK: # if tracking a sink mark instruction as sink
            instruction.markAsSink()
            print 'Marking as sink: ', instruction
            trackTree.addComment(blockIdx, instructionIdx, 'Marked instruction ' + ' as sink.')
            return
        else:                           # if tracking a source continue tracking
            # Function is called on a source object. Track the result.
            if instruction.parameters()[-1][-1] == 'V': # it returns a void
                print 'Function', instruction.parameters()[-1], 'called on source object, but returns void'
            else:
                print 'Function', instruction.parameters()[-1], 'called on source object, tracking result'

                trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree)

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
                trackFromCall(trackType, method, blockIdx, instructionIdx, trackTree, instruction.parameters()[0])
            else: 
                # It was a static call, track the object that was returned, if any
                if instruction.parameters()[-1].endswith(')V'): # it does not return a void
                    print 'Tracking the object returned'
                    instruction.markAsSink()
                    trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree)
            
        
        for _, instructionMethod in usages:
            
            print 'Tracking recursively.....'
            parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)

            trackFromCall(trackType, instructionMethod, 0, 0, trackTree, parameterRegister)
                
        if instruction.parameters()[-1][-1] != 'V': # It returns something
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree)
            
            
    elif instruction.type() == InstructionType.IF:
        # The register is used in a if statement
        print 'Register is used in if statement'
        
    elif instruction.type() == InstructionType.FIELDPUT:
        # The content of the register is put inside a field, either of an instance or a class. Use trackFieldUsages to
        # lookup where this field is read and continue tracking there
        parameters = instruction.parameters()
        print 'Data is put in field', parameters[-2], 'of class', parameters[-3]

        trackFieldUsages(trackType, parameters[-3], parameters[-2], parameters[-1], trackTree)
        
    elif instruction.type() == InstructionType.ARRAYPUT:
        if parameterIndex == 0: # Data is put in an array. Track the array
            print "Data is put in an array"
            newRegister = instruction.parameters()[1] # target array
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath, newRegister)
        else:
            # Something else is put into the array being tracked (param = 1), or it is used as index (param = 2)
            print "Data is put in source array or used as index"
        
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
        
    elif instruction.type() == InstructionType.ARRAYGET:
        if parameterIndex == 0:
            # Data is put into the tracked register, the register is overwritten
            print 'Register was overwritten'
            return True
        elif parameterIndex == 1:
            # Data is taken out of tainted Array, assume this data is tainted as well
            print 'Data read from tainted array'
            newRegister = instruction.parameters()[0] # target register
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackedPath, newRegister)
        elif parameterIndex == 2:
            print 'Tainted data used as index for array'
        
    elif instruction.type() == InstructionType.RETURN:
        # Register is used in return instruction. use trackMethodUsages to look for usages of this function and track
        # the register containing the result.
        
        print 'Data was returned. Looking for usages of this function' 
        
        trackMethodUsages(trackType, method.memberOf().name(), method.name(), trackTree)
        
    elif instruction.type() == InstructionType.MOVE:
        # Value is moved into other register. When first parameter the register is overwritten, else the value is
        # copied into another register. Track that register as well.
        
        if parameterIndex == 0:
            print 'Register was overwritten'
            return True
        else:
            newRegister = instruction.parameters()[0]
            print 'Data copied into new register', newRegister

            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree, newRegister)
        
    else:
        # Uncaught instruction used
        # TODO: new-instance
        print 'Unknown operation performed'

    

# Track a register from the specified block and instrucion index in the provided method. If no register is provided,
# attempt to read the register to track from the move-result instruction on the instruction specified.
def trackFromCall(trackType, method, startBlockIdx, startInstructionIdx, trackTree, register = None):
    if startInstructionIdx >= len(method.blocks()[startBlockIdx].instructions()):
        # Instruction is out of bounds, see if there is a next block. 
        if len(method.blocks()[startBlockIdx].nextBlocks()) == 0 :
            # Out of list bounds!
            print "WARNING: Out of bounds!"
            return
        else: # Continue tracking in the next blocks
            for block in method.blocks()[startBlockIdx].nextBlocks():
                trackFromCall(trackType, method, block.index(), 0, trackTree, register)
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
    
    # Tree creation
    node = Tree(trackTree, identifier) # If trackTree = None it means this will be the root node
    if not (trackTree is None):
        trackTree.addChild(node)
    
        if trackTree.inBranch(identifier):
            node.addComment(startBlockIdx, startInstructionIdx, 'Recursion: Already tracked this method.')
            print 'RECURSION: Already tracked this register in this method, aborting'
            print 'identifier', method, startBlockIdx, startInstructionIdx, register
            return
    
    print '>', method.memberOf().name(), method.name()
    print 'Tracking the result in register', register
    
    firstBlock = method.blocks()[startBlockIdx]
    analyzeBlocks(trackType, method, firstBlock, startInstructionIdx, node, [], register)
    
    print
    if trackTree is None:
        trackedTrees.append(node) #node.toHTML()#toString()

def analyzeBlocks(trackType, method, block, startInstructionIdx, trackTree, trackedBlocks, register):   
    if block.index() in trackedBlocks:
        return  # Recursion, stop tracking
    
    trackedBlocks = trackedBlocks + [block.index()]
    # Inspect all instruction for usage of the register
    for instruction in block.instructions()[startInstructionIdx:]: 
        if register in instruction.parameters():
            
            if instruction.type() == InstructionType.MOVERESULT:
                return # register is overwritten
            
            overwritten = analyzeInstruction(trackType, method, instruction, register, trackTree)

            if overwritten:
                return # register is overwritten
    
    # Recursively analyze all next blocks
    for nextBlock in block.nextBlocks():
        analyzeBlocks(trackType, method, nextBlock, 0, trackTree, trackedBlocks, register)
        
 
    
def trackMethodUsages(trackType, className, methodName, trackTree):
    methods = structure.calledMethodsByMethodName(className, methodName)
    #print 'Method', methodName, className 
    if len(methods): 
        print '---------------------------------------------------'
        print 'Method', methodName, className, 'is used in', len(methods), 'method(s):\n' 
    
    # search through all the methods where it is called
    for method in methods:
        
        indices = method.calledInstructionsByMethodName(className, methodName)
        for blockIdx, instructionIdx in indices:
            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree) 

def trackFieldUsages(trackType, className, fieldName, type, trackTree):
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

            trackFromCall(trackType, method, blockIdx, instructionIdx + 1, trackTree, register)

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
                    trackFromCall(TrackType.SOURCE, method, 0, 0, None, 'v' + str(parameterNumber))

def trackSink(className, methodName, isSink, direct):
    methods = structure.calledMethodsByMethodName(className, methodName)
    
    for method in methods:
        print 'New', className, 'created in', method.name()
        indices = method.calledInstructionsByMethodName(className, methodName)
        # Track it and mark new sinks
        for idx in indices:
            if 'is-sink' in isSink:
                instruction = method.blocks()[idx[0]].instructions()[idx[1]]
                trackFromCall(TrackType.SINK, method, idx[0], idx[1], None, instruction.parameters()[0])
            else:
                trackFromCall(TrackType.SINK, method, idx[0], idx[1] + 1, None)
                

def main():
    point = time.time()

    classAndFunctions, fields, listeners = sources('api_sources.txt')
    sinkClasses = sinks('api_sinks.txt')
    global structure
    global trackedTrees
    trackedTrees = []
    
    structure = APKstructure('apks/nl.peperzaken.android.nu-1.apk')
    #trackSockets.structure = structure
    
    # search for and mark sinks
    for className, methodName, isSink, direct in sinkClasses:
        trackSink(className, methodName, isSink, direct)

    print
    
    # search for all data receiving listeners
    for _, _, superClassName, methods in listeners:
        trackListenerUsages(superClassName, methods)

    print
    
    # search for all tainted methods
    for className, methodName in classAndFunctions:
        trackMethodUsages(TrackType.SOURCE, className, methodName, None)
        
    for className, fieldName, type in fields:
        trackFieldUsages(TrackType.SOURCE, className, fieldName, type, None)
    

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
    

