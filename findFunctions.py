#!/usr/bin/env python

import re
import sys
import trackSockets

sys.path.append('androguard')

from androlyze import *
from structure import *
from tools import *
 
# Read the list of api sources       
def sources(filename) :
    with open(filename) as sourcesFile:
        sources = sourcesFile.readlines()
        
    functions = []
        
    for line in sources[1:]:
        classAndFunction = line.split()[0:2]
        if classAndFunction != []:
            classAndFunction[0] = classAndFunction[0].replace('.', '/')
            classAndFunction[0] = 'L' + classAndFunction[0] + ';'
            functions.append(classAndFunction)
            
    return functions
        
# these functions are here to keep my head clear
def method(idx, analysis):
    return analysis.get_method(analysis.get_vm().get_methods()[idx])

def block(idx, method):
    return method.get_basic_blocks().get()[idx]

def instruction(idx, block):
    return block.get_instructions()[idx]


def analyzeInstruction(method, instruction, register):
    print instruction.opcode(), instruction.parameters()
    
    if instruction.isSink():
        print 'Value is put in sink!'
        return
    
    parameterIndex = instruction.parameters().index(register)
    
    if 'invoke' in instruction.opcode():
        # attempt to find the method used within the apk
        _, instructionMethod= instruction.classAndMethodByStructure(structure)
        if not (instructionMethod is None):
            print 'Information is used in method call defined in apk'
            print 'Tracking recursively.....'
            parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)
            trackFromCall(instructionMethod, 0, 0, parameterRegister)
            
            # Parameter p* is tainted in method instructionMethod, taint it and continue tracking
        else:  
            # class is not defined within APK
            className, methodName = instruction.classAndMethod()
            print 'Method', methodName, 'not found in class', className
            
            
    elif 'if-' in instruction.opcode():
        print 'Register is used in if statement'
    
    elif 'put' in instruction.opcode():
        print 'Value is put in field'
        #Value is put inside array, 'aput'
        #Value is put in instance field, 'iput'
        #Value is put in static field, 'sput'
        
    elif 'return' in instruction.opcode():
        print 'Value was returned. Looking for usages of this function' 
        
        trackUsages(method.memberOf().name(), method.name())
        
    elif 'move' in instruction.opcode():
        print 'move'
        #Value is moved into other register, 'move'
        
    else:
        print 'Unknown operation performed'

    

def trackFromCall(method, blockIdx, instructionIdx, register = None):
    if register is None:
        resultInstruction = method.blocks()[blockIdx].instructions()[instructionIdx]
        if resultInstruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
            register = resultInstruction.parameters()[0]
            instructionIdx += 1 # move the pointer to the instruction after the move-result
        else:
            print "No move-result instruction was found for", method.blocks()[blockIdx].instructions()[instructionIdx]
            return
        
    
    print '>', method.name()
    print 'Tracking the result in register', register
    
    
    for block in method.blocks()[blockIdx:]:
        startIdx = instructionIdx if block == method.blocks()[blockIdx] else 0
        for instruction in block.instructions()[startIdx:]:
            if register in instruction.parameters():
                
                if instruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
                    return # register is overwritten
                
                analyzeInstruction(method, instruction, register)
                
    print
    
def trackUsages(className, methodName):
    methods = structure.calledMethodsByMethodName(className, methodName)
    #print 'Method', methodName, className 
    if len(methods): 
        print '---------'
        print 'Method', methodName, className, 'is used in:\n' 
    
    # search through all the methods where it is called
    for method in methods:
        
        indices = method.calledInstructionsByMethodName(className, methodName)
        for blockIdx, instructionIdx in indices:
            trackFromCall(method, blockIdx, instructionIdx + 1) 

def main():
    point = time.time()

    classAndFunctions = sources('api_sources.txt')
    global structure

    structure = APKstructure('apks/LeakTest1.apk')
    trackSockets.structure = structure
    
    # find socket creations (or other known sinks)
    methods = structure.calledMethodsByMethodName('Ljava/net/Socket;', 'getOutputStream')

    for method in methods:
        print 'Socket created in', method.name()
        indices = method.calledInstructionsByMethodName('Ljava/net/Socket;', 'getOutputStream')
        # Track it and mark new sinks
        for idx in indices:
            trackSockets.trackFromCall(method, idx[0], idx[1] + 1)

    # find file creations
    # track file objects:
    methods = structure.calledMethodsByMethodName('Ljava/io/File;', '<init>')
    for method in methods:
        print 'New File created in', method.name()
        indices = method.calledInstructionsByMethodName('Ljava/io/File;', '<init>')
        # Track it and mark new sinks
        for idx in indices:
            register = method.blocks()[idx[0]].instructions()[idx[1]]
            trackSockets.trackFromCall(method, idx[0], idx[1] + 1, register.parameters()[0])

    # track file output streams
    methods = structure.calledMethodsByMethodName('Ljava/io/FileOutputStream;', '<init>')
    for method in methods:
        print 'New FileOutputStream created in', method.name()
        indices = method.calledInstructionsByMethodName('Ljava/io/FileOutputStream;', '<init>')
        # Track it and mark new sinks
        for idx in indices:
            register = method.blocks()[idx[0]].instructions()[idx[1]]
            trackSockets.trackFromCall(method, idx[0], idx[1] + 1, register.parameters()[0])
    
    print
        
    # search for all tainted methods
    for className, methodName in classAndFunctions:
        trackUsages(className, methodName)
    

    print 'total time: ', time.time() - point 

if __name__=="__main__":
    main()
    


#get_name: type of instruction
#get_output: argument to instruction
#get_literals: variables

