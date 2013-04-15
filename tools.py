#!/usr/bin/env python

import sys

sys.path.append('androguard')

from androlyze import *

class Method :
    def __init__(self, methodInfo):
        self.d_method = methodInfo
        self.d_blocks = []
        for block in methodInfo.get_basic_blocks().get() :
            self.d_blocks.append(block)
            
    def method(self):
        return self.d_method
    
    def blocks(self):
        return self.d_blocks

class APKstructure :
    def __init__(self, dvm, analysis):
        self.d_methods = {}
        self.d_dvm = dvm
        self.d_analysis = analysis
        for method in dvm.get_methods() :
            self.d_methods[method.get_name()] = Method(analysis.get_method(method))
            
    def method(self, name):
        return self.d_methods[name]
    
    def methods(self):
        return self.d_methods
    
    def dvm(self):
        return self.d_dvm
    
    def analysis(self):
        return self.d_analysis
    

def analyse(file) :
    _, d, dx = AnalyzeAPK(file, False, 'dad')
    return APKstructure(d, dx)

def forEveryInstruction(function, method) :
    if method.method().get_method().get_code() == None:
        return

    # search through all blocks
    for block in method.blocks(): 
        # search through all instructions
        for instruction in block.get_instructions():   
            function(instruction)
           
def printInstructionsWithNames(file, instructionNames) :
    structure = analyse(file)

    def printIfInstruction(instruction) :
        if instruction.get_name() in instructionNames :
            print instruction.get_name(), instruction.get_output()

    # search through all methods
    for method in structure.methods() :
        forEveryInstruction(printIfInstruction, structure.method(method))
        
        
        