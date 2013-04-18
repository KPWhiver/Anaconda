#!/usr/bin/env python

import re
import sys

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


def analyzeInstruction(instruction, register):
    print instruction.opcode(), instruction.parameters()
    
    parameterIndex = instruction.parameters().index(register)

    if 'invoke' in instruction.opcode():
        className, methodName = instruction.classAndMethod()
        
        # attempt to find the method used within the apk
        instructionClass = structure.classByName(className)
        if not (instructionClass is None):
            instructionMethod = instructionClass.methodByName(methodName)
            if not (instructionMethod is None) and instructionMethod.hasCode():
                print 'Information is used in method call defined in apk'
                print 'Tracking recursively.....'
                parameterRegister = 'v%d' % (instructionMethod.numberOfLocalRegisters() + parameterIndex)
                trackFromCall(instructionMethod, parameterRegister, 0, 0)
                
                # Parameter p* is tainted in method instructionMethod, taint it and continue tracking
            else:
                # method is not defined within APK
                print 'Method', methodName, 'not found in class', className
        else:  
            # class is not defined within APK
            print 'Class' , className, 'not found in apk'
            if [className, methodName] in []: # is the method a known sink?
                print 'data is leaking'
            
    elif 'if-' in instruction.opcode():
        print 'Register is used in if statement'
    
    elif 'put' in instruction.opcode():
        print 'Value is put in field'
        #Value is put inside array, 'aput'
        #Value is put in instance field, 'iput'
        #Value is put in static field, 'sput'
        
    elif 'return' in instruction.opcode():
        print 'Value was returned'
        
    elif 'move' in instruction.opcode():
        print 'move'
        #Value is moved into other register, 'move'
        
    else:
        print 'Unknown operation performed'

    

def trackFromCall(method, blockIdx, instructionIdx):
    resultInstruction = method.blocks()[blockIdx].instructions()[instructionIdx]
    if resultInstruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
        register = resultInstruction.parameters()[0]
    else:
        print "No move-result instruction was found for", method.blocks()[blockIdx].instructions()[instructionIdx]
        return
        
    instructionIdx += 1 # set it 
    print '>', method.name()
    print 'Tracking the result in register', register
    for block in method.blocks()[blockIdx:]:
        startIdx = instructionIdx if block == method.blocks()[blockIdx] else 0
        for instruction in block.instructions()[startIdx:]:
            if register in instruction.parameters():
                
                if instruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
                    return # register is overwritten
                
                analyzeInstruction(instruction, register)
                
    print
     
def analyzeBlocks(method, classAndFunctions):
    
    previousWasSource = False
    
    # search through all blocks
    for blockIdx, block in enumerate(method.blocks()): 

        # search through all instructions
        for instructionIdx, instruction in enumerate(block.instructions()):
            # search for indirect calls (constructors are always direct (either that or java is even weirder than I thought))
            if instruction.opcode() in ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface']:
                previousWasSource = False
                className, methodName = instruction.classAndMethod()
                
                if [className, methodName[0:methodName.find('(')]] in classAndFunctions:
                    print className, methodName
                    previousWasSource = True
                    
                elif className == 'Ljava/net/Socket;' and methodName == '<init>':
                    print className, methodName
                    
            if instruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide'] and previousWasSource:
                trackFromCall(method, instruction.parameters()[0], blockIdx, instructionIdx + 1)

def main():
    point = time.time()

    classAndFunctions = sources('api_sources.txt')
    global structure
    structure = APKstructure('apks/LeakTest1.apk')
    
    # find socket creations (or other known sinks)
    methods = structure.calledMethodByName('Ljava/net/Socket;', '<init>')
    for method in methods:
        print 'Socket created in', method.name()
        method.calledInstructionByName('Ljava/net/Socket;', '<init>')
        # Track it and mark new sinks
    
    print
    
    # search for all tainted methods
    for className, methodName in classAndFunctions:
        methods = structure.calledMethodByName(className, methodName)
        if len(methods): print 'Method', methodName, 'is used in:\n'
        # search through all the methods where it is called
        for method in methods:
            
            indices = method.calledInstructionByName(className, methodName)
            for blockIdx, instructionIdx in indices:
                trackFromCall(method, blockIdx, instructionIdx + 1) 
        if len(methods): print '---------'
    
    

    print 'total time: ', time.time() - point 

    """# search through all classes
    for _, jvmClass in structure.classes().items():
    
        # search through all methods
        for _, method in jvmClass.methods().items():
    
            if not method.hasCode():
                continue
            
            analyzeBlocks(method, classAndFunctions)"""
            
if __name__=="__main__":
    main()
    


#get_name: type of instruction
#get_output: argument to instruction
#get_literals: variables

