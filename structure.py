import sys, re, time

sys.path.append('androguard')

from androlyze import *

# enum class with opcodes as fields
class InstructionType :
    NONE = -1
    NOP = 0
    MOVE = 1
    RETURN = 2
    IF = 3
    ARRAYGET = 4
    FIELDGET = 5
    ARRAYPUT = 6
    FIELDPUT = 7
    INVOKE = 8

def parseOpcode(opcode):
    if 'nop' in opcode:
        return InstructionType.NOP
    elif 'move' in opcode:
        return InstructionType.MOVE
    elif 'return' in opcode:
        return InstructionType.RETURN
    elif 'if-' in opcode:
        return InstructionType.IF
    elif 'aget' in opcode:
        return InstructionType.ARRAYGET
    elif 'get' in opcode:
        return InstructionType.FIELDGET
    elif 'aput' in opcode:
        return InstructionType.ARRAYPUT
    elif 'put' in opcode:
        return InstructionType.FIELDPUT
    elif 'invoke' in opcode:
        return InstructionType.INVOKE
    else:
        return InstructionType.NONE

# variables for parsing
classParse = '(\[*L[\w/\$_]*;)'
whitespaceParse = '[\s]*'


# parse the last argument of a function call
def parseInvoke(call) :    
    match = re.match(classParse + '->(.*)', call)
    if match == None:
        print 'error: ', call
        return '', ''
    
    return match.group(1), match.group(2)

def parseFieldGet(call) :
    #if call != '' and call[0] == '[':
    #    return '', ''
    # ^ ???
    
    match = re.match(classParse + '->([\w_]*)' + whitespaceParse + '(\[*L[\w/\$_]*;|\[*[VZBSCIJFD])', call)
    if match == None:
        print 'error: ', call
        return '', '', ''
    
    return match.group(1), match.group(2), match.group(3)

# replace 'v1 ... v3' with 'v1', 'v2', 'v3'
def replaceRange(parameters):
    match = re.match('v([\d]+)' + whitespaceParse + '\.\.\.' + whitespaceParse + 'v([\d]+)', parameters[0])
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
    
    def __init__(self, instruction):        
        self.d_instruction = instruction
        self.d_parameters = [arg.strip() for arg in instruction.get_output().split(',')]
        self.d_isSink = False
        self.d_type = parseOpcode(instruction.get_name())
        
        # if the argument is a range convert it
        if len(self.d_parameters) > 0 and '...' in self.d_parameters[0]:
            replaceRange(self.d_parameters)
        
        # if this instruction is a function call parse the function (there is also something like invoke-quick?)
        if self.d_type == InstructionType.INVOKE:
            calledClass, calledMethod = parseInvoke(self.d_parameters[-1]) 
            self.d_parameters[-1] = calledClass
            self.d_parameters.append(calledMethod)
        elif self.d_type == InstructionType.FIELDGET or self.d_type == InstructionType.FIELDPUT:
            calledClass, calledField, type = parseFieldGet(self.d_parameters[-1])
            self.d_parameters[-1] = calledClass
            self.d_parameters += [calledField, type]
        
    # androguard instruction object
    def instruction(self):
        return self.d_instruction
    
    # type of instruction, e.g. 'invoke-virtual'
    def opcode(self):
        return self.d_instruction.get_name()
    
    # type of instruction as int
    def type(self):
        return self.d_type
    
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
    
    # the Class object and Method object this instruction is calling (deprecated)
    def classAndMethodByStructure(self, structure):  
        classObject = structure.classByName(self.d_parameters[-2])
        if classObject is None:
            return None, None
        
        return classObject, classObject.methodByName(self.d_parameters[-1])
    
    # the Class objects and Method objects this instruction is possibly calling (possibly due to inheritance)
    def classesAndMethodsByStructure(self, structure):       
        classObject = structure.classByName(self.d_parameters[-2])        
        if classObject is None:
            return []
        
        # is it a static call that's executed virtually
        virtualStatic = 'invoke-static' in self.opcode() and classObject.methodByName(self.d_parameters[-1]) is None
        
        if 'invoke-virtual' not in self.opcode() and 'invoke-interface' not in self.opcode() and not virtualStatic:
            superClass = classObject.superClass()
            if 'invoke-super' in self.opcode() and superClass.dvmClass() is None:
                return []
            elif 'invoke-super' in self.opcode():
                return [[superClass, superClass.methodByName(self.d_parameters[-1])]]
            else:
                return [[classObject, classObject.methodByName(self.d_parameters[-1])]]
        
        classes = [classObject] + classObject.subClasses() # TODO make unique + recursive
        
        classesAndMethods = []
        
        for classObject in classes:
            method = classObject.methodByName(self.d_parameters[-1])
            if not (method is None):
                classesAndMethods += [classObject, method]
                
        return classesAndMethods
    
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
    def calledInstructionsByMethodName(self, className, methodName):
        list = []
        for blockIdx, block in enumerate(self.d_blocks):
            for instructionIdx, instruction in enumerate(block.instructions()):
                if instruction.type() == InstructionType.INVOKE and className in instruction.parameters()[-2] and methodName in instruction.parameters()[-1]:                
                    list.append([blockIdx, instructionIdx])
        
        return list
    
    # indices in the list of Block object and the list of Instruction objects within that, where the given field is accessed
    def calledInstructionsByFieldName(self, className, fieldName):
        list = []
        for blockIdx, block in enumerate(self.d_blocks):
            for instructionIdx, instruction in enumerate(block.instructions()):
                if instruction.type() == InstructionType.FIELDGET and className in instruction.parameters()[-3] and fieldName in instruction.parameters()[-2]:                
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
    # if jvmClass is None we can't find the class
    def __init__(self, jvmClass = None, analysis = None):
        self.d_class = jvmClass
        self.d_methods = {}
        
        if(jvmClass is None):
            self.d_initialized = True
        else:
            self.d_initialized = False
        
        self.d_analysis = analysis
        
        self.d_superClass = None
        self.d_subClasses = []
        self.d_haveRecursiveSearched = False

    # add subclasses this class has
    def addSubclass(self, subClasses):
        self.d_subClasses.append(subClasses) # TODO: duplicates?

    # subClasses of this class
    def subClasses(self):
        if self.d_haveRecursiveSearched == False:
            self._addSubClassesRecursively()
            
        return self.d_subClasses
    
    def _addSubClassesRecursively(self):
        self.d_haveRecursiveSearched = True
        
        newList = []
        
        for subClass in self.d_subClasses:
            newList += subClass.subClasses()
            
        self.d_subClasses += newList
        set = {}
        map(set.__setitem__, self.d_subClasses, [])
        self.d_subClasses = set.keys()

    # androguard class
    def dvmClass(self):
        return self.d_class
    
    # source code in java of this class
    def sourceCode(self):
        return self.dvmClass().source()
    
    # superclass of this class
    def superClass(self):
        return self.d_superClass
    
    # set superclass of this class
    def setSuperClass(self, superclass):
        self.d_superClass = superclass
    
    # name of superclass of this class
    def superClassName(self):
        return self.d_class.get_superclassname()
    
    def interfaceNames(self):
        interfacesString = self.d_class.get_interfaces()
        if interfacesString is None:
            return []
        interfacesString.replace('(', '')
        interfacesString.replace(')', '')
        return interfacesString.split(' ')

    # name of the class
    def name(self):
        if self.d_class is None:
            return 'Java API class'
            
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
           
        # add subclasses to classes
        for _, classObject in self.d_classes.items():
            superClasses = [classObject.superClassName()] + classObject.interfaceNames()

            # loop through all super classes of this class and add this class as subclass
            for superClass in superClasses:
                superClassObject = self.d_classes.get(superClass, None)
                if superClassObject is None:
                    superClassObject = Class()
                    self.d_classes[superClass] = superClassObject
                    
                classObject.setSuperClass(superClassObject)
                superClassObject.addSubclass(classObject)
                        
        print 'parse time: ', time.time() - point

    # dictionary of Class objects by name
    def classes(self):
        return self.d_classes
    
    # Class object with a certain name
    def classByName(self, name):
        return self.d_classes.get(name, None)
    
    # Method objects in which the given method is called
    def calledMethodsByMethodName(self, className, methodName):
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
            classObject = self.classByName(location[0])
            if classObject is None:
                print 'error couldn\'t find class ', location[0]
                continue
            method = classObject.methodByName(location[1] + location[2])
            if method is None:
                print 'error couldn\'t find method ', location[1] + location[2], ' in class ', location[0]
                continue
            
            methods.append(method)
            
        return methods
    
    # Method objects in which the given field is accessed, descriptor is type
    def calledMethodsByFieldName(self, className, fieldName, descriptor):
        
        pathps = self.d_analysis.tainted_variables.get_field(className, fieldName, descriptor).get_paths()
        methods = []
        
        for data, methodIdx in pathps:
            
            # we are only interested in field reads
            if data[0] == 'W':
                continue
            
            # find the Method object that is associated with this path
            className, methodName, parameters = self.d_dvm.get_cm_method(methodIdx)
            methodName += parameters[0] + parameters[1]
            
            classObject = self.classByName(className)
            if classObject is None:
                print 'error couldn\'t find class ', className
                continue
            method = classObject.methodByName(methodName)
            if method is None:
                print 'error couldn\'t find method ', methodName, ' in class ', className
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
