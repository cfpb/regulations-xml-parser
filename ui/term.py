class Term:

    def __init__(self, term, start, end, notice=None, def_location=None):

        self.term = term
        self.start = start
        self.end = end
        self.start_index = '1.0+{}c'.format(self.start)
        self.end_index = '1.0+{}c'.format(self.end)
        self.notice = notice
        self.def_location = def_location

    def __str__(self):

        if self.notice and self.def_location:
            return '{}: {} ({})'.format(self.term, self.def_location, self.notice)
        else:
            return '{} [{}]'.format(self.term, self.start)

    def __hash__(self):

        return hash((self.term, self.def_location))