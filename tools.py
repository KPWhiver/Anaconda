#!/usr/bin/env python

import sys, re

import structure
reload(structure)

sys.path.append('androguard')

from androlyze import *


# execute function for all instructions
def forEveryInstruction(function, method):
    if not method.hasCode():
        return

    # search through all blocks
    for block in method.blocks(): 
        # search through all instructions
        for instruction in block.instructions():   
            function(instruction)
          
# prints a minimal call graph of a class (commented out because of issues, will fix later)
"""
def printBlocks(file, className):
    structure = structure.APKstructure(file)

    def printBlock(block):
        for instruction in block.instructions():   
            print instruction.opcode(), instruction.parameters()
            
    # note: this takes an androguard block
    def printRecursive(block):
        printBlock(block)
        print '->'
        for child in block.block().get_next():
            printRecursive(child[2])
            print '+'
            

    # search through all methods
    jvmClass = structure.classByName(className)

    for _, method in jvmClass.methods().items():
        # search through all blocks
        printRecursive(method.blocks()[0])
        print '\n\n'
        #for block in method.blocks():
        #    printBlock(block)
        #    print '_'
"""

# print all instruction with a certain name (for example: 'invoke-direct') 
def printInstructions(file, instructionNames):
    struct = structure.APKstructure(file)

    def printIfInstruction(instruction):
        if instruction.opcode() in instructionNames:
            print '\t', instruction
            
    #jvmClass = struct.classByName('Lcom/example/leaktest1/MainActivity;')
    #method = jvmClass.methodByName('onCreate(Landroid/os/Bundle;)V')
    
    # search through all methods
    for _, jvmClass in struct.classes().items():
 
        for _, method in jvmClass.methods().items():

            print method
            forEveryInstruction(printIfInstruction, method)
    
        
        