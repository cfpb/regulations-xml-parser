from dateutil import parser as date_parser

from lxml import etree

from inflect import engine

from operator import itemgetter


class Notice:

    def __init__(self, filename):

        self.filename = filename
        self.terms = []
        self.modified = False
        self.effective_date = None

        with open(filename, 'r') as f:
            reg_xml = f.read()
            parser = etree.XMLParser(huge_tree=True)
            self.tree = etree.fromstring(reg_xml, parser)
            reg = self.tree.find('{eregs}preamble')
            if reg is not None:
                self.document_number = reg.find('{eregs}documentNumber').text
            else:
                changeset = self.tree.find('{eregs}changeset')
                if changeset:
                    self.document_number = changeset.get('rightDocumentNumber')
                else:
                    raise ValueError('Not a RegML file!')
            eff_date = self.tree.find('.//{eregs}effectiveDate').text
            self.effective_date = date_parser.parse(eff_date)

    def __str__(self):

        return '<Notice: {}>'.format(self.document_number)

    def extract_terms(self):

        definitions = self.tree.findall('.//{eregs}def')
        self.terms = []
        inf = engine()

        for defn in definitions:
            defined_in = defn.find('../..').get('label')
            term = defn.get('term')
            plural = inf.plural(term)
            self.terms.append((term, defined_in, self.document_number))
            self.terms.append((plural, defined_in, self.document_number))

        self.terms.sort(key=itemgetter(0))

    @property
    def defined_terms(self):

        if not self.terms:
            self.extract_terms()

        return self.terms

    def replace_node(self, label, new_element):

        current_element = self.tree.find('.//{}[@label="{}"]'.format(new_element.tag, label))
        if not current_element:
            current_element = self.tree.find('.//{{eregs}}{}[@label="{}"]'.format(new_element.tag, label))
        if not current_element:
            raise ValueError('Element {} not found!'.format(new_element.tag))

        current_element_parent = current_element.find('..')
        current_element_parent.replace(current_element, new_element)
        self.modified = True

    def save(self):

        with open(self.filename, 'w') as f:
            f.write(etree.tostring(self.tree, pretty_print=True, encoding='UTF-8'))

        self.modified = False