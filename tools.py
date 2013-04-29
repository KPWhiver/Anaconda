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
def printBlocks(file, className):
    struct = structure.APKstructure(file)
            
    # note: this takes an androguard block
    def printRecursive(block, prevList, indent):
        print block.smali(indent + '    ')
        
        if block.nextBlocks() != []:
            print indent, '->'
        
        for nextBlock in block.nextBlocks():
            if nextBlock in prevList:
                print nextBlock.smali(indent + '        ')
                print indent, '      ', 'found recursion, abort!'
                if not (nextBlock is block.nextBlocks()[-1]):
                    print indent, '+'
                continue

            printRecursive(nextBlock, prevList + [nextBlock], indent + '    ')
            
            if not (nextBlock is block.nextBlocks()[-1]):
                print indent, '+'
            

    # search through all methods
    classObject = struct.classByName(className)

    for _, method in classObject.methods().items():
        print method
        # search through all blocks
        printRecursive(method.blocks()[0], [], '')
        print '\n\n'
        #for block in method.blocks():
        #    printBlock(block)
        #    print '_'


# print all instruction with a certain name (for example: 'invoke-direct') 
def printInstructions(file):
    struct = structure.APKstructure(file)


    jvmClass = struct.classByName('Lcom/example/leaktest1/MainActivity;')
    #method = jvmClass.methodByName('onCreate(Landroid/os/Bundle;)V')
    
    # search through all methods
    #for _, jvmClass in struct.classes().items():
 
    for _, method in jvmClass.methods().items():
        print method
        
        for block in method.blocks():
            print block.smali('    ')
            print '    ', block.block().get_prev()
        #print method
        #forEveryInstruction(printIfInstruction, method)
    
        
        