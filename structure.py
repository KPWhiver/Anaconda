import sys, re, time

sys.path.append('androguard')

from androlyze import *

# Parse the last argument of a function call
def parseCall(call) :
    if call != '' and call[0] == '[':
        return '', ''
    
    match = re.match('(L[\w/\$]*;)->(.*)', call)
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
    invokeOpcodes = ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface', 
                     'invoke-direct/range', 'invoke-virtual/range', 'invoke-super/range', 'invoke-static/range', 'invoke-interface/range']

    def __init__(self, instruction):        
        self.d_instruction = instruction
        self.d_parameters = [arg.strip() for arg in instruction.get_output().split(',')]
        
        # if the argument is a range convert it
        if len(self.d_parameters) > 0 and '...' in self.d_parameters[0]:
            replaceRange(self.d_parameters)
        
        # if this instruction is a function call parse the function (there is also something like invoke-quick?)
        if instruction.get_name() in Instruction.invokeOpcodes:
            calledClass, calledMethod = parseCall(self.d_parameters[-1]) 
            self.d_parameters[-1] = calledClass
            self.d_parameters.append(calledMethod)
        
        
    def instruction(self):
        return self.d_instruction
        
    def opcode(self):
        return self.d_instruction.get_name()
        
    def parameters(self):
        return self.d_parameters
        
    def classAndMethod(self):
        if self.d_parameters > 1:
            return self.d_parameters[-2], self.d_parameters[-1]
        
        return None, None
    """
    def classAndMethodByStructure(self, structure):
        if self.d_parameters > 1:
            return self.d_parameters[-2], self.d_parameters[-1]
        
        return structure.classByName(self.d_parameters[-2]), structureF@*& C@
    """
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
    def __init__(self, methodInfo, classObject):
        self.d_class = classObject
        self.d_method = methodInfo
        self.d_blocks = []
        for block in methodInfo.get_basic_blocks().get():
            self.d_blocks.append(Block(block))
            
        self.d_name = methodInfo.get_method().get_name() + methodInfo.get_method().get_descriptor()
        self.d_name.replace(' ', '')
            
    # MethodAnalysis object
    def method(self):
        return self.d_method
    
    # Name of the function
    def name(self):
        return self.d_name
    
    def memberOf(self):
        return self.d_class
    
    def calledInstructionByName(self, className, methodName):
        list = []
        for blockIdx, block in enumerate(self.d_blocks):
            for instructionIdx, instruction in enumerate(block.instructions()):
                if instruction.opcode() in Instruction.invokeOpcodes and className in instruction.parameters()[-2] and methodName in instruction.parameters()[-1]:                
                    list.append([blockIdx, instructionIdx])
        
        return list
                
    def numberOfRegisters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_registers_size()
        else:
            return None    
        
    def numberOfParameters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_ins_size()
        else:
            return None
        
    def numberOfLocalRegisters(self):
        if self.hasCode():
            return self.numberOfRegisters() - self.numberOfParameters()
        else:
            return 0
    
    # Does the function contain code
    def hasCode(self):
        return self.d_method.get_method().get_code() is not None
    
    # The code blocks
    def blocks(self):
        return self.d_blocks
    
    def __str__(self):
        return self.name()

class Class:
    def __init__(self, jvmClass, analysis):
        self.d_class = jvmClass
        self.d_methods = {}
        self.d_initialized = False
        self.d_analysis = analysis

    def name(self):
        return self.d_class.get_name()
            
    def methods(self):
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods      
    
    def methodByName(self, name):
        # if no methods in this class parse them
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods.get(name, None)
    
    def __str__(self):
        return self.name()
    
    def _initializeMethods(self):
        self.d_initialized = True

        for method in self.d_class.get_methods():
            newMethod = Method(self.d_analysis.get_method(method), self)
            self.d_methods[newMethod.name()] = newMethod

            
class APKstructure:
    def __init__(self, file):
        point = time.time()
        _, self.d_dvm, self.d_analysis = AnalyzeAPK(file, False, 'dad')
        
        self.d_classes = {}
        for jvmClass in self.d_dvm.get_classes():
            self.d_classes[jvmClass.get_name()] = Class(jvmClass, self.d_analysis)
        print 'parse time: ', time.time() - point

    def classes(self):
        return self.d_classes
    
    def classByName(self, name):
        return self.d_classes.get(name, None)
    
    def calledMethodByName(self, className, methodName, descriptor = '.'):
        pathps = self.d_analysis.tainted_packages.search_methods(className, methodName, descriptor)
        methods = []
        for path in pathps:
            # find the Method object that is associated with this path
            location = path.get_src(self.d_dvm.get_class_manager())
            jvmClass = self.classByName(location[0])
            if jvmClass is None:
                print 'error couldn\'t find class ', location[0]
                continue
            method = jvmClass.methodByName(location[1] + location[2])
            if method is None:
                print 'error couldn\'t find method ', location[1] + location[2]
                continue
            
            methods.append(method)
            
        return methods
    
    def dvm(self):
        return self.d_dvm
    
    def analysis(self):
        return self.d_analysis
    
    def __str__(self):
        return ''
