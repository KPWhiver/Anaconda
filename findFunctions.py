#!/usr/bin/env python

import re
import sys

sys.path.append('androguard')

from androlyze import *
from tools import *

# Parse the last argument of a function call
def parseCall(call) :
    if call != '' and call[0] == '[':
        return '', ''
    
    match = re.match('L([\w/\$]*);->([\w\$<>]*)\(.*', call)
    if match == None:
        print call
        return '', ''
    
    return match.group(1), match.group(2)
 
# Read the list of api sources       
def sources(filename) :
    with open(filename) as sourcesFile:
        sources = sourcesFile.readlines()
        
    functions = []
        
    for line in sources[1:]:
        classAndFunction = line.split()[0:2]
        if classAndFunction != []:
            classAndFunction[0] = classAndFunction[0].replace('.', '/')
            functions.append(classAndFunction)
            
    return functions
        
# these functions are here to keep my head clear
def method(idx, analysis) :
    return analysis.get_method(analysis.get_vm().get_methods()[idx])

def block(idx, method) :
    return method.get_basic_blocks().get()[idx]

def instruction(idx, block) :
    return block.get_instructions()[idx]


def trackFromCall(method, register, blockIdx, instructionIdx) :
    for block in method.blocks()[blockIdx:] :
        startIdx = instructionIdx if block == method.blocks()[blockIdx] else 0
        for instruction in block.get_instructions()[startIdx:] :
            print 'track'
     
def analyzeBlocks(method, classAndFunctions):
    
    previousWasSource = False
    
    # search through all blocks
    for blockIdx, block in enumerate(method.blocks()): 

        # search through all instructions
        for instructionIdx, instruction in enumerate(block.get_instructions()):
            
            instructionArgs = [arg.strip() for arg in instruction.get_output().split(',')]
            
            
            # search for indirect calls (constructors are always direct (either that or java is even weirder than I thought))
            if instruction.get_name() in ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface']:
                previousWasSource = False
                className, methodName = parseCall(instructionArgs[-1])
                if [className, methodName] in classAndFunctions:
                    print className, methodName
                    previousWasSource = True
                    
                elif className == 'java/net/Socket' and methodName == '<init>':
                    print className, methodName
                    
            if instruction.get_name() in ['move-result-object', 'move-result', 'move-result-wide'] and previousWasSource :
                trackFromCall(method, instructionArgs[0], blockIdx, instructionIdx)


def main() :

    classAndFunctions = sources('api_sources.txt')

    structure = APKstructure('apks/LeakTest1.apk')

    

    # search through all classes
    for _, jvmClass in structure.classes().items() :
    
        # search through all methods
        for _, method in jvmClass.methods().items() :
    
            if not method.hasCode() :
                continue
    
            analyzeBlocks(method, classAndFunctions)
            
if __name__=="__main__":
    main()
    


#get_name: type of instruction
#get_output: argument to instruction
#get_literals: variables

