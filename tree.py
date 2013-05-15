import jinja2
import string

def reindent(s, indent):
    s = string.split(s, '\n')
    s = [indent + string.lstrip(line) for line in s]
    s = string.join(s, '\n')
    return s



class Tree:
    
    def __init__(self, parent, content):
        self.d_children = []
        self.d_comments = {}
        self.d_node_comments = []
        self.d_parent = parent
        self.d_content = content
        self.d_leakText = ''
        
    def addChild(self, child):
        self.d_children.append(child)

    def addComment(self, instruction, register, comment):
        dictValue = self.d_comments.get(instruction, None)
        # Make sure multiline comments are nicely outlined
        comment = comment.replace('\n', '\n  |          ' + len(register) * ' ')
        commentWithSyntax = '  |------> ' + register + ': ' + comment + '\n'

        if dictValue is None:
            self.d_comments[instruction] = commentWithSyntax
        else:
            self.d_comments[instruction] += commentWithSyntax

    def addNodeComment(self, comment):
        self.d_node_comments.append(str(comment) + '\n')
        
    def inBranch(self, content):
        if content == self.d_content:
            return True
        elif not (self.d_parent is None):
            return self.d_parent.inBranch(content)
        
        return False
    
    def content(self):
        return self.d_content
    
    def uniqueId(self):
        return id(self)
    
    def setLeakText(self, text):
        if self.d_leakText == '':
            self.d_leakText = text
    
    def toString(self, prepend = ''):
        output = '<>' + prepend + self.d_content[0].method().name() + ' ' + self.d_content[1] + '\n'
        
        for child in self.d_children:
            output += child.toString(prepend + '    ')
            
        return output
    
    """
    def toHTML(self, prepend = ''):
        output = ''
        
        if self.d_parent is None:
            output += '<div class="tree">\n'
            output += '<ul><li>\n'
            
        output += prepend + '<a href="#c' + str(self.uniqueId()) + '">' + self.d_leaks * "Leaks: " + self.d_content[0].method().name() + '<br>start-register: ' + self.d_content[1] + '</a>\n'
        
        if len(self.d_children) > 0:
            output += prepend + '<ul>\n'
        
        for child in self.d_children:
            output += prepend + '<li>\n'
            output += child.toHTML(prepend + '  ')
            output += prepend + '</li>\n'
            
        if len(self.d_children) > 0:
            output += prepend + '</ul>\n'
            
        if self.d_parent is None:
            output += '</li></ul>\n'
            output += '</div>\n'
            
        return output
    """
        
    def toHTML(self, prepend = ''):
        output = ''
        
        if self.d_parent is None:
            output += '<div class="tree">\n'
            output += '<ol>\n'
            
        # This branch has been tracked already somewhere else
        if 'Stopping' in self.d_content[1]:
            name = '<span style="color:#f00">' + self.d_leakText + '</span>' + self.d_content[0].method().name() + ' ' + self.d_content[1]
        else:
            name = '<span style="color:#f00">' + self.d_leakText + '</span>' + self.d_content[0].method().name() + ' start-register: ' + self.d_content[1]
            
        if len(self.d_children) == 0:
            output += prepend + '<li class="file"><a href="#c' + str(self.uniqueId()) + '">' + name + '</a></li>\n'
        else:
            output += prepend + '<li>\n'
            output += prepend + '<label class="folder" for="' + str(self.uniqueId()) + '"><a href="#c' + str(self.uniqueId()) + '">' + name + '</a></label>\n'
            output += prepend + '<input type="checkbox" id="' + str(self.uniqueId()) + '" />\n'
            output += prepend + '<ol>\n'
            
            for child in self.d_children:
                output += child.toHTML(prepend + '  ')
            
            output += prepend + '</ol>\n'
            output += prepend + '</li>\n'
            
        if self.d_parent is None:
            output += '</ol>\n'
            output += '</div>\n'
            
        return output

    def comments(self, instruction, indent):
        comment = self.d_comments.get(instruction, None)
        newcomment = ''
        if comment is not None:
            newcomment = '<span style="color:#3f3">'
            newcomment += reindent('  |\n' + comment, indent + '    ')
            newcomment += '</span>\n'
            
        return newcomment

    def printRecursive(self, block, visited, indent):
        output = ''
        number = block.number()
        
        # print all instructions in this block
        for index, instruction in enumerate(block.instructions()):
            # if index is 0 we want to print the unique number of the block
            if index == 0:
                output += number + indent[len(number):]
            else:
                output += indent
                
            output += instruction.__str__() + ' '#instruction.smali()
            if instruction.isSink():
                output += '(marked as sink)'
               
            output += '\n'
            
            output += self.comments(instruction, indent)
        
        # if next blocks we need to draw the arrow
        if block.nextBlocks() != []:
            output += indent + '->\n'
        
        # go to all next blocks
        for index, nextBlock in enumerate(block.nextBlocks()):
            if not (visited.get(nextBlock, None) is None):
                #output += nextBlock.smali(indent + '    ')
                output += indent + '    ' + 'Go to: ' + nextBlock.number() + '\n'#'found recursion, abort!\n'
                if not (nextBlock is block.nextBlocks()[-1]):
                    output += indent + '+\n'
                continue
            
            visited[nextBlock] = True

            output += self.printRecursive(nextBlock, visited, indent + '    ')
            
            if not (nextBlock is block.nextBlocks()[-1]):
                output += indent + '+\n'

        return output


    def listComments(self):
        output = ''
        
        # This branch has been tracked already somewhere else
        if 'Stopping' in self.d_content[1]:
            output += '<h5>' + self.d_content[0].method().memberOf().name() + '->' + self.d_content[0].method().name() + ' ' + self.d_content[1] + '</h5>'
            return output
       
        output += '<h5>' + self.d_content[0].method().memberOf().name() + '->' + self.d_content[0].method().name() + ' start-register: ' + self.d_content[1] + '</h5>'
        output += '<div class="comment" id="c'+ str(self.uniqueId()) +'">'
        
        output += '<pre>'
        
        output += self.d_content[0].method().sourceCode()
        
        output += '</pre>'
        output += '<pre>'
        
        if self.d_node_comments:
            output += 'Node information:\n\n'
            for comment in self.d_node_comments:
                output += comment
            output += '\n------------------------------\n\n'
        
        firstBlock = self.d_content[0].method().blocks()[0]
        visited = {}
        output += self.comments(None, '')
        output += self.printRecursive(firstBlock, visited, '    ') + '\n'

        output += '</pre>'
        output += '</div>'

        for child in self.d_children:
            output += child.listComments()

        return output
    
