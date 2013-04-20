import sys, re, time

sys.path.append('androguard')

from androlyze import *

# parse the last argument of a function call
def parseCall(call) :
    if call != '' and call[0] == '[':
        return '', ''
    
    match = re.match('(L[\w/\$]*;)->(.*)', call)
    if match == None:
        print 'error: ', call
        return '', ''
    
    return match.group(1), match.group(2)

# replace 'v1 ... v3' with 'v1', 'v2', 'v3'
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
    
    # remove first 'ranged' parameter
    parameters.pop(0)
    
    for number in range(firstInt, secondInt + 1):
        parameters.insert(number - firstInt, 'v' + str(number))
        

# class containing information about a single construction
class Instruction:
    invokeOpcodes = ['invoke-direct', 'invoke-virtual', 'invoke-super', 'invoke-static', 'invoke-interface', 
                     'invoke-direct/range', 'invoke-virtual/range', 'invoke-super/range', 'invoke-static/range', 'invoke-interface/range']

    def __init__(self, instruction):        
        self.d_instruction = instruction
        self.d_parameters = [arg.strip() for arg in instruction.get_output().split(',')]
        self.d_isSink = False
        
        # if the argument is a range convert it
        if len(self.d_parameters) > 0 and '...' in self.d_parameters[0]:
            replaceRange(self.d_parameters)
        
        # if this instruction is a function call parse the function (there is also something like invoke-quick?)
        if instruction.get_name() in Instruction.invokeOpcodes:
            calledClass, calledMethod = parseCall(self.d_parameters[-1]) 
            self.d_parameters[-1] = calledClass
            self.d_parameters.append(calledMethod)
        
    # androguard instruction object
    def instruction(self):
        return self.d_instruction
    
    # type of instruction, e.g. 'invoke-virtual'
    def opcode(self):
        return self.d_instruction.get_name()
    
    # mark this instruction as being a sink    
    def markAsSink(self):
        self.d_isSink = True
        
    # is this instruction a sink
    def isSink(self):
        return self.d_isSink
    
    # parameters of opcode, e.g. registers, and other things like method to call
    def parameters(self):
        return self.d_parameters
        
    # the name of the class and method this instruction is calling
    def classAndMethod(self):
        if self.d_parameters > 1:
            return self.d_parameters[-2], self.d_parameters[-1]
        
        return None, None
    
    # the Class object and Method object this instruction is calling
    def classAndMethodByStructure(self, structure):       
        classObject = structure.classByName(self.d_parameters[-2])
        if classObject is None:
            return None, None
        
        return classObject, classObject.methodByName(self.d_parameters[-1])
    
    def __str__(self):
        return self.opcode() + str(self.d_parameters)
        
# class containing information about a single block (for example all the different scopes in a method)
class Block:
    def __init__(self, block):
        self.d_block = block
        self.d_instructions = []
        for instruction in block.get_instructions():
            self.d_instructions.append(Instruction(instruction))
        
    # androguard block
    def block(self):
        return self.d_block
        
    # Instruction objects within this block
    def instructions(self):
        return self.d_instructions
    
    def __str__(self):
        return ''

# class containing information about a single method
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
    
    # name of the function
    def name(self):
        return self.d_name
    
    # Class object this method is a member of
    def memberOf(self):
        return self.d_class
    
    # indices in the list of Block object and the list of Instruction objects within that, where the given method is called
    def calledInstructionByName(self, className, methodName):
        list = []
        for blockIdx, block in enumerate(self.d_blocks):
            for instructionIdx, instruction in enumerate(block.instructions()):
                if instruction.opcode() in Instruction.invokeOpcodes and className in instruction.parameters()[-2] and methodName in instruction.parameters()[-1]:                
                    list.append([blockIdx, instructionIdx])
        
        return list
                
    # number of registers e.g. v1, v2, v3 etc (this includes the parameters)
    def numberOfRegisters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_registers_size()
        else:
            return None    
        
    # number of parameters
    def numberOfParameters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_ins_size()
        else:
            return None
        
    # number of registers without the parameters
    def numberOfLocalRegisters(self):
        if self.hasCode():
            return self.numberOfRegisters() - self.numberOfParameters()
        else:
            return 0
    
    # does the function contain code
    def hasCode(self):
        return self.d_method.get_method().get_code() is not None
    
    # list of Block objects
    def blocks(self):
        return self.d_blocks
    
    def __str__(self):
        return self.name()

# class containing information about a single class
class Class:
    def __init__(self, jvmClass, analysis):
        self.d_class = jvmClass
        self.d_methods = {}
        self.d_initialized = False
        self.d_analysis = analysis

    # name of the class
    def name(self):
        return self.d_class.get_name()
            
    # dictionary containing the Method objects by name
    def methods(self):
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods      
    
    # Method object with a certain name
    def methodByName(self, name):
        # if no methods in this class parse them
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods.get(name, None)
    
    def __str__(self):
        return self.name()
    
    # initializes the dictionary of Method objects, only called when needed
    def _initializeMethods(self):
        self.d_initialized = True

        for method in self.d_class.get_methods():
            newMethod = Method(self.d_analysis.get_method(method), self)
            self.d_methods[newMethod.name()] = newMethod

# class containing information about an entire APK file
class APKstructure:
    def __init__(self, file):
        point = time.time()
        _, self.d_dvm, self.d_analysis = AnalyzeAPK(file, False, 'dad')
        
        self.d_classes = {}
        for jvmClass in self.d_dvm.get_classes():
            self.d_classes[jvmClass.get_name()] = Class(jvmClass, self.d_analysis)
        print 'parse time: ', time.time() - point

    # dictionary of Class objects by name
    def classes(self):
        return self.d_classes
    
    # Class object with a certain name
    def classByName(self, name):
        return self.d_classes.get(name, None)
    
    # Method objects in which the given method is called
    def calledMethodByName(self, className, methodName):
        # search_methods requires regexp's, this makes sure it gets them
        descriptorLoc = methodName.find('(')
        if descriptorLoc == -1:
            descriptor = '.'
        else:
            descriptor = methodName[descriptorLoc:]
            descriptor = descriptor.replace('(', '\(')
            descriptor = descriptor.replace(')', '\)')
            descriptor = descriptor.replace('$', '\$')
            methodName = methodName[0:descriptorLoc]
        
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
    
    # androguard DalvikVMFormat
    def dvm(self):
        return self.d_dvm
    
    # androguard uVMAnalysis
    def analysis(self):
        return self.d_analysis
    
    def __str__(self):
        return ''
