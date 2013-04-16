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
            
    # MethodAnalysis object
    def method(self):
        return self.d_method
    
    # Name of the function
    def name(self):
        return self.d_method.get_method().get_name()
    
    # Does the function contain code
    def hasCode(self):
        return self.d_method.get_method().get_code() != None
    
    # The code blocks
    def blocks(self):
        return self.d_blocks

class Class :
    def __init__(self, jvmClass, analysis):
        self.d_class = jvmClass
        self.d_methods = {}
        for method in jvmClass.get_methods() :
            self.d_methods[method.get_name()] = Method(analysis.get_method(method))
            
    def methods(self):
        return self.d_methods      
    
    def methodByName(self, name):
        return self.d_methods[name]  
            
class APKstructure :
    def __init__(self, file):
        _, self.d_dvm, self.d_analysis = AnalyzeAPK(file, False, 'dad')
        self.d_classes = {}
        for jvmClass in self.d_dvm.get_classes():
            self.d_classes[jvmClass.get_name()] = Class(jvmClass, self.d_analysis)

    def classes(self):
        return self.d_classes
    
    def classByName(self, name):
        return self.d_classes[name]
    
    def dvm(self):
        return self.d_dvm
    
    def analysis(self):
        return self.d_analysis

def forEveryInstruction(function, method) :
    if not method.hasCode():
        return

    # search through all blocks
    for block in method.blocks(): 
        # search through all instructions
        for instruction in block.get_instructions():   
            function(instruction)
           
def printInstructionsWithNames(file, instructionNames) :
    structure = APKstructure(file)

    def printIfInstruction(instruction) :
        if instruction.get_name() in instructionNames :
            print instruction.get_name(), instruction.get_output()

    # search through all methods
    for _, jvmClass in structure.classes().items() :
        for _, method in jvmClass.methods().items() :
            forEveryInstruction(printIfInstruction, method)
        
        
        