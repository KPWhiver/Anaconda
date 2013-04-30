class Tree:
    
    def __init__(self, parent, content):
        self.d_children = []
        self.d_parent = parent
        self.d_content = content
        
    def addChild(self, child):
        self.d_children.append(child)
        
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
            
        output += prepend + '<a href="#">' + self.d_content[0].name() + '<br>' + str(self.d_content[1]) + ' ' + str(self.d_content[2]) + ' ' + self.d_content[3] + '</a>\n'
        
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