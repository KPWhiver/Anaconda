#!/usr/bin/env python

import re
import sys

sys.path.append('androguard')

from androlyze import *

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
    for block in method.get_basic_blocks().get()[blockIdx:] :
        startIdx = instructionIdx if block == method.get_basic_blocks().get()[blockIdx] else 0
        for instruction in block.get_instructions()[startIdx:] :
            print 'track'
     
def main() :

    # 

    classAndFunctions = sources('api_sources.txt')

    a, d, dx = AnalyzeAPK('apks/LeakTest1.apk', False, "dad")

    # search through all methods
    for method in d.get_methods():
        methodInfo = dx.get_method(method)
        
        method.get_class_name()

        if method.get_code() == None:
            continue

        # search through all blocks
        for blockIdx, block in enumerate(methodInfo.get_basic_blocks().get()): 

            # search through all instructions
            for instructionIdx, instruction in enumerate(block.get_instructions()):
                
                instructionArgs = [arg.strip() for arg in instruction.get_output().split(',')]
                
                previousSource = False
                
                # search for indirect calls (constructors are always direct (either that or java is even weirder than I thought))
                if instruction.get_name() in ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface']:
                    previousSource = False
                    className, methodName = parseCall(instructionArgs[-1])
                    if [className, methodName] in classAndFunctions:
                        # trackFromCall(methodInfo, blockIdx, instructionIdx)
                        print className, methodName
                        previousSource = True
                        
                if instruction.get_name() in ['move-result-object', 'move-result', 'move-result-wide'] and previousSource :
                    trackFromCall(methodInfo, instructionArgs[0], blockIdx, instructionIdx)
                           
            
  
  
if __name__=="__main__":
    main()
    


#get_name: type of instruction
#get_output: argument to instruction
#get_literals: variables

