import jinja2

class Tree:
    
    def __init__(self, parent, content):
        self.d_children = []
        self.d_comments = {}
        self.d_parent = parent
        self.d_content = content
        
    def addChild(self, child):
        self.d_children.append(child)

    def addComment(self, blockIdx, instructionIdx, comment):
        dictValue = self.d_comments.get((blockIdx, instructionIdx), None)
        commentWithSyntax = '\t\t' + comment + '\n'

        if dictValue is None:
            self.d_comments[(blockIdx, instructionIdx)] = commentWithSyntax
        else:
            self.d_comments[(blockIdx, instructionIdx)] += commentWithSyntax
        
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
        output = '<>' + prepend + self.d_content[0].name() + ' ' + self.d_content[3] + '\n'
        
        for child in self.d_children:
            output += child.toString(prepend + '    ')
            
        return output
    
    def toHTML(self, prepend = ''):
        output = ''
        
        if self.d_parent is None:
            output += '<div class="tree">\n'
            output += '<ul><li>\n'
            
        output += prepend + '<a href="#">' + self.d_content[0].name() + '<br>blockIdx: ' + str(self.d_content[1]) + ', instructionIdx: ' + str(self.d_content[2]) + ', register: ' + self.d_content[3] + '</a>\n'
        
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

    def listComments(self):
        output = ''

        output += '<pre>'
        
        for blockIdx, block in enumerate(self.d_content[0].blocks()):
            for instructionIdx, instruction in enumerate(block.instructions()):
                output += instruction.smali()
                output += self.d_comments.get((blockIdx, instructionIdx), '')

        output += '</pre>'

        for child in self.d_children:
            output += child.listComments()

        return output


   # structure.classByNAme
   # methodByName

   # for block in method
   #     for instruction in block
   #         enumerate