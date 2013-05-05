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
        
    def addChild(self, child):
        self.d_children.append(child)

    def addComment(self, instruction, comment):
        dictValue = self.d_comments.get(instruction, None)
        commentWithSyntax = '  |------> ' + comment + '\n'

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
    
    def toString(self, prepend = ''):
        output = '<>' + prepend + self.d_content[0].method().name() + ' ' + self.d_content[1] + '\n'
        
        for child in self.d_children:
            output += child.toString(prepend + '    ')
            
        return output
    
    def toHTML(self, prepend = ''):
        output = ''
        
        if self.d_parent is None:
            output += '<div class="tree">\n'
            output += '<ul><li>\n'
            
        output += prepend + '<a href="#c' + str(self.uniqueId()) + '">' + self.d_content[0].method().name() + '<br>register: ' + self.d_content[1] + '</a>\n'
        
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

    def printRecursive(self, block, prevList, indent):
        output = ''
        for instruction in block.instructions():
            output += indent + instruction.smali()
            comment = self.d_comments.get(instruction, None)
            if comment is not None:
                output += reindent('  |\n' + comment, indent + '  ')
                output += '\n'
        
        if block.nextBlocks() != []:
            output += indent + '->\n'
        
        for nextBlock in block.nextBlocks():
            if nextBlock in prevList:
                output += nextBlock.smali(indent + '  ')
                output += indent + '  ' + 'found recursion, abort!\n'
                if not (nextBlock is block.nextBlocks()[-1]):
                    output += indent + '+\n'
                continue

            output += self.printRecursive(nextBlock, prevList + [nextBlock], indent + '  ')
            
            if not (nextBlock is block.nextBlocks()[-1]):
                output += indent + '+\n'

        return output


    def listComments(self):

        output = ''
        output += '<h5>' + str(self.d_content[0].method()) + '</h5>'
        output += '<pre class="comment" id="c'+ str(self.uniqueId()) +'">'
        
        if self.d_node_comments:
            output += 'Node information:\n\n'
            for comment in self.d_node_comments:
                output += comment
            output += '\n------------------------------\n\n'
        
        firstBlock = self.d_content[0].method().blocks()[0]
        output += self.printRecursive(firstBlock, [], '') + '\n'

        output += '</pre>'

        for child in self.d_children:
            output += child.listComments()

        return output
    