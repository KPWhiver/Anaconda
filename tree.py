import jinja2

class Tree:
    
    def __init__(self, parent, content):
        self.d_children = []
        self.d_comments = {}
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
            
        output += prepend + '<a href="#">' + self.d_content[0].method().name() + '<br>register: ' + self.d_content[1] + '</a>\n'
        
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

        output += '<h4>' + str(self.d_content[0].method()) + '</h4>'

        output += '<pre>'
        
        for block in self.d_content[0].method().blocks():
            for instruction in block.instructions():
                output += instruction.smali()
                comment = self.d_comments.get(instruction, None)
                if comment is not None:
                    output += '  |\n' + comment + '\n'

        output += '</pre>'

        for child in self.d_children:
            output += child.listComments()

        return output


   # structure.classByNAme
   # methodByName

   # for block in method
   #     for instruction in block
   #         enumerate