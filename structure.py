import sys, re

sys.path.append('androguard')

from androlyze import *

# Parse the last argument of a function call
def parseCall(call) :
    if call != '' and call[0] == '[':
        return '', ''
    
    match = re.match('(L[\w/\$]*;)->([\w\$<>]*)\(.*', call)
    if match == None:
        print 'error: ', call
        return '', ''
    
    return match.group(1), match.group(2)

def replaceRange(parameters):
    match = re.match('v([\d]+)[\s]*\.\.\.[\s]*v([\d]+)', parameters[0])
    if match == None:
        print 'error: ', parameters
        return
    
    firstInt = int(match.group(1))
    secondInt = int(match.group(2))
    
    if secondInt < firstInt or firstInt == None or secondInt == None:
        print 'error: ', parameters
        return
    
    parameters.pop(0)
    
    for number in range(firstInt, secondInt + 1):
        parameters.insert(number - firstInt, 'v' + str(number))
        
class Instruction:
    def __init__(self, instruction):
        self.d_instruction = instruction
        self.d_parameters = [arg.strip() for arg in instruction.get_output().split(',')]
        # this could possibly be done with inheritance?
        self.d_calledClass = None
        self.d_calledMethod = None
        
        # if the argument is a range convert it
        if len(self.d_parameters) > 0 and '...' in self.d_parameters[0]:
            replaceRange(self.d_parameters)
        
        # if this instruction is a function call parse the function (there is also something like invoke-quick?)
        if instruction.get_name() in ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface']:
            self.d_calledClass, self.d_calledMethod = parseCall(self.d_parameters[-1]) 
        elif instruction.get_name() in ['invoke-direct/range', 'invoke-virtual/range', 'invoke-super/range', 'invoke-static/range', 'invoke-interface/range']:
            self.d_calledClass, self.d_calledMethod = parseCall(self.d_parameters[-1])
        
    def instruction(self):
        return self.d_instruction
        
    def opcode(self):
        return self.d_instruction.get_name()
        
    def parameters(self):
        return self.d_parameters
        
    def classAndMethod(self):
        return self.d_calledClass, self.d_calledMethod
    
    def __str__(self):
        return self.opcode() + str(self.d_parameters)
        
class Block:
    def __init__(self, block):
        self.d_block = block
        self.d_instructions = []
        for instruction in block.get_instructions():
            self.d_instructions.append(Instruction(instruction))
        
    def block(self):
        return self.d_block
        
    def instructions(self):
        return self.d_instructions
    
    def __str__(self):
        return ''

class Method:
    def __init__(self, methodInfo):
        self.d_method = methodInfo
        self.d_blocks = []
        for block in methodInfo.get_basic_blocks().get():
            self.d_blocks.append(Block(block))
            
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
    
    def __str__(self):
        return self.name()

class Class:
    def __init__(self, jvmClass, analysis):
        self.d_class = jvmClass
        self.d_methods = {}
        for method in jvmClass.get_methods():
            self.d_methods[method.get_name()] = Method(analysis.get_method(method))
            
    def name(self):
        return self.d_class.get_name()
            
    def methods(self):
        return self.d_methods      
    
    def methodByName(self, name):
        return self.d_methods[name]  
    
    def __str__(self):
        return self.name()
            
class APKstructure:
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
    
    def __str__(self):
        return ''
