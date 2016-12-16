import os

import Tkinter as tk
import tkFileDialog
import tkMessageBox
import tkSimpleDialog
import ttk
import inflect
import cPickle

from lxml import etree
from notice import Notice
from regml import find_all
from regulation.node import find_all_occurrences, enclosed_in_tag, interpolate_string
from operator import itemgetter
from itertools import chain

def xml_node_text(node, include_children=True):
    """
    Extract the raw text from an XML element.

    :param node: the XML element, usually ``<content>``.
    :type node: :class:`etree.Element`
    :param include_children: whether or not to get the text of the children as well.
    :type include_children: :class:`bool` - optional, default = True

    :return: a string of the text of the node without any markup.
    :rtype: :class:`str`
    """

    if node.text:
        node_text = node.text
    else:
        node_text = ''

    if include_children:
        for child in node.getchildren():
            if child.text:
                node_text += child.text
            if child.tail:
                node_text += child.tail

    else:
        for child in node.getchildren():
            if child.tail:
                node_text += child.tail.strip()

    return node_text


class EregsApp(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.master = master
        self.grid(sticky=tk.N+tk.S+tk.E+tk.W)

        self.notices = []
        self.notices_files = []
        self.trees = {}
        self.current_notice = None
        self.current_node = None
        self.root_notice = None
        self.root_notice_file = None
        self.terms = []
        self.always_fix = set()
        self.never_fix = set()
        self.inf = inflect.engine()
        self.initialize_gui()
        self.work_state_filename = None

    def initialize_gui(self):

        menubar = tk.Menu(self.master)
        menu_file = tk.Menu(menubar)
        menu_action = tk.Menu(menubar)
        menubar.add_cascade(menu=menu_file, label='File')
        menubar.add_cascade(menu=menu_action, label='Action')
        menu_file.add_command(label='Open root notice', command=self.open_root_notice)
        menu_file.add_command(label='Open additional notices', command=self.open_additional_notice)
        menu_file.add_command(label='Load work state', command=self.load_work_state)
        menu_file.add_separator()
        menu_file.add_command(label='Save modified notices', command=self.save)
        menu_file.add_separator()
        menu_file.add_command(label='Quit', command=self.master.quit)#, accelerator='Ctrl+Q')
        menu_action.add_command(label='Scan node for terms', command=self.scan_current_node_for_terms)
        self.master.bind_all('<Control-d>', self.scan_current_node_for_terms)
        self.master.bind_all('<Control-s>', self.save)
        self.master.bind_all('<Control-f>', self.fix_selected_refs)

        self.notices_list = tk.Listbox(self)
        self.notices_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        self.notices_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.notices_list.yview)
        self.notices_list.configure(yscrollcommand=self.notices_scroll.set)
        self.master.config(menu=menubar)
        self.element_tree = ttk.Treeview(self)
        self.element_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)

        self.center_panel = tk.Frame(self)
        self.center_panel.pack(side=tk.LEFT, expand=tk.YES)
        self.xml_text = tk.Text(self.center_panel, wrap=tk.WORD, height=35)
        self.xml_text.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self.preview_text = tk.Text(self.center_panel, wrap=tk.WORD, height=35)
        self.preview_text.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)

        self.right_panel = tk.Frame(self, relief='sunken')
        self.right_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)

        self.definitions = tk.Listbox(self.right_panel, width=400)
        self.definitions.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self.definitions_scroll = ttk.Scrollbar(self.right_panel, orient=tk.VERTICAL, command=self.definitions.yview)
        self.definitions.configure(selectmode=tk.EXTENDED)
        #self.definitions_scroll.pack(side=tk.RIGHT)

        self.unmarked_defs = tk.Listbox(self.right_panel, width=400)
        self.unmarked_defs.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self.unmarked_defs.bind('<<ListboxSelect>>', self.highlight_selected_terms)
        self.unmarked_defs.bind('<Double-Button-1>', self.focus_on_term)
        self.unmarked_defs.configure(selectmode=tk.EXTENDED)
        self.fix_defs = tk.Button(self.right_panel, text='Fix selected references', command=self.fix_selected_refs)
        self.fix_defs.pack(side=tk.TOP)

        self.element_tree.bind('<Button-1>', self.select_tree_element)
        self.notices_list.bind('<Button-1>', self.select_notice)
        self.definitions.bind('<Button-2>', self.terms_context_menu)

        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.master.columnconfigure(1, weight=1)
        self.master.columnconfigure(2, weight=2)
        self.master.columnconfigure(3, weight=2)

    def open_root_notice(self):

        load_root = False

        if self.root_notice is not None:
            message = "You already have a root notice loaded. If you load " + \
            "another root notice, your current set of notices will be replaced. " + \
            "Are you sure you want to do this?"
            result = tkMessageBox.askokcancel('Replace root?', message)
            if result:
                load_root = True
        else:
            load_root = True

        if load_root:
            self.notices = []
            self.root_notice = None
            self.current_notice = None
            self.trees = {}
            for child in self.element_tree.get_children():
                self.element_tree.delete(child)

            notice_file = tkFileDialog.askopenfilename()
            if notice_file:
                notice = Notice(notice_file)
                self.current_notice = notice.document_number
                self.notices.append(notice.document_number)
                self.root_notice = notice
                self.root_notice_file = notice_file
                self.add_element_to_tree(notice.tree, None)
                self.update_notices_list()
                self.trees[notice.document_number] = self.root_notice
                self.populate_definitions()

                cfr_section = notice.tree.find('{eregs}preamble').find('.//{eregs}section').text
                all_notice_files = find_all(cfr_section, is_notice=True)

                message = "There are {} additional notices associated with this root version. ".format(len(all_notice_files)) + \
                    "Would you like to load all of them? This can take some time if the notices " + \
                    "are very large."
                result = tkMessageBox.askokcancel('Load all notices?', message)
                if result:
                    self.notices_files = all_notice_files
                    all_notices = [Notice(notice_file) for notice_file in all_notice_files]
                    all_notices.sort(key=lambda n: n.effective_date)
                    for notice in all_notices:
                        self.notices.append(notice.document_number)
                        self.trees[notice.document_number] = notice

                    self.update_notices_list()
                    self.populate_definitions()

    def open_additional_notice(self):

        notice_file = tkFileDialog.askopenfilename()

        if notice_file:
            replace_notice = True
            notice = Notice(notice_file)
            if notice.document_number in self.notices:
                message = 'You already have this notice loaded. If you reload it, ' + \
                    'your unsaved work will be replaced. Are you sure you want to do this?'
                replace_notice = tkMessageBox.askokcancel('Replace notice?', message)

            if replace_notice:
                self.notices.append(notice.document_number)
                self.notices_files.append(notice_file)
                self.trees[notice.document_number] = notice
                self.update_notices_list()
                self.populate_definitions()

    def load_work_state(self, event=None):

        message = 'Any unsaved work that you have open will be lost. Continue?'
        load_work = tkMessageBox.askyesno('Load work state?', message)

        if load_work:
            work_state_file = tkFileDialog.askopenfilename()
            if work_state_file:
                self.work_state_filename = work_state_file
                work_state = cPickle.load(open(self.work_state_filename, 'r'))
                self.root_notice_file = work_state['root_notice']
                self.notices_files = work_state['open_notices']
                self.terms = work_state['definitions']
                self.always_fix = work_state['always_fix']
                self.never_fix = work_state['never_fix']

                self.root_notice = Notice(self.root_notice_file)
                self.current_notice = self.root_notice.document_number
                self.add_element_to_tree(self.root_notice.tree, None)
                self.trees[self.root_notice.document_number] = self.root_notice
                self.populate_definitions()
                self.notices.append(self.root_notice.document_number)

                notices = [Notice(notice_file) for notice_file in self.notices_files]
                notices.sort(key=lambda n: n.effective_date)

                for notice in notices:
                    self.notices.append(notice.document_number)
                    self.trees[notice.document_number] = notice

                self.update_notices_list()
                self.populate_definitions()

    def save(self, event=None):

        for notice in self.trees.itervalues():
            if notice.modified:
                print 'Saving {}'.format(notice.document_number)
                notice.save()

        self.save_work_state()

    def save_work_state(self):

        work_state = {'root_notice': self.root_notice_file,
                      'open_notices': self.notices_files,
                      'definitions': self.gather_defined_terms(),
                      'always_fix': self.always_fix,
                      'never_fix': self.never_fix}

        if self.work_state_filename is None or not os.path.exists(self.work_state_filename):
            self.work_state_filename = tkFileDialog.asksaveasfilename()

        cPickle.dump(work_state, open(self.work_state_filename, 'w'))

    def select_notice(self, item):

        selection = self.notices_list.curselection()[0]
        doc_number = self.notices_list.get(selection)
        self.current_notice = doc_number
        notice = self.trees[doc_number]
        for child in self.element_tree.get_children():
            self.element_tree.delete(child)
        self.add_element_to_tree(notice.tree, None)

    def update_notices_list(self):

        self.notices_list.delete(0, tk.END)
        for i, notice in enumerate(self.notices):
            self.notices_list.insert(tk.END, notice)

    def select_tree_element(self, item):

        xmlns_prop = """xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance\" """
        if self.current_notice is not None and self.trees != {}:
            selection = self.element_tree.item(self.element_tree.focus())
            selected_text = selection['text']
            notice = self.trees[self.current_notice]
            if 'changeset' in selected_text:
                element = notice.tree.find('{eregs}changeset')
            else:
                label = selection['text']
                element = notice.tree.find('.//*[@label="{}"]'.format(label))
            self.current_node = element

            if element is not None and element.tag.replace('{eregs}', '') in \
                    ['paragraph', 'interpParagraph', 'section',
                     'interpSection', 'appendixSection', 'changeset', 'change']:
                self.set_xml_text(etree.tostring(element, pretty_print=True).replace(xmlns_prop, ''))
                self.set_preview_text(element)
                self.scan_current_node_for_terms()

    def set_xml_text(self, text):

        if self.xml_text.get('1.0', 'end') != '':
            self.xml_text.delete('1.0', 'end')
        self.xml_text.insert('end', text)

    def set_preview_text(self, element_to_render):

        if self.preview_text.get('1.0', 'end') != '':
            self.preview_text.delete('1.0', 'end')

        def insert_text(element):
            if element.tag.replace('{eregs}', '') in ['section', 'interpSection', 'appendixSection',
                                                      'changeset', 'change']:
                subject = element.find('.//{eregs}subject')
                if subject is not None:
                    self.preview_text.insert('end', subject.text + '\n', ('section_header',))
                for child in element.getchildren():
                    insert_text(child)

            elif element.tag.replace('{eregs}', '') in ['paragraph', 'interpParagraph']:
                marker = element.get('marker', '')
                for child in element.getchildren():
                    if child.tag.replace('{eregs}', '') == 'title':
                        self.preview_text.insert('end', marker + ' ' + child.text + '\n', ('par_header',))
                    elif child.tag.replace('{eregs}', '') == 'content':
                        if child.text:
                            self.preview_text.insert('end', child.text)
                        for gchild in child.getchildren():
                            self.preview_text.insert('end', gchild.text, (gchild.tag.replace('{eregs}', ''),))
                            if gchild.tail:
                                self.preview_text.insert('end', gchild.tail)
                        self.preview_text.insert('end', '\n')
                    elif child.tag.replace('{eregs}', '') in ['paragraph', 'interpParagraph']:
                        insert_text(child)

        insert_text(element_to_render)

        self.preview_text.tag_configure('section_header', font='helvetica 14 bold')
        self.preview_text.tag_configure('ref', background='green')
        self.preview_text.tag_configure('def', background='orange')

    def add_element_to_tree(self, element, parent):

        label = element.get('label', None)
        doc_number = element.get('rightDocumentNumber', None)
        if parent is None and label is not None:
            item_id = self.element_tree.insert('', 'end', text=label)
        elif parent is not None and label is not None:
            item_id = self.element_tree.insert(parent, 'end', text=label)
        elif doc_number is not None and parent is None:
            item_id = self.element_tree.insert('', 'end', text='changeset: {}'.format(doc_number))
        else:
            item_id = parent

        for child in element.getchildren():
            self.add_element_to_tree(child, item_id)

    def populate_definitions(self):

        self.definitions.delete(0, tk.END)
        terms = self.gather_defined_terms()
        for i, defn in enumerate(terms):
            self.definitions.insert(tk.END, '{}: {} ({})'.format(defn[0], defn[1], defn[2]))
            if (defn[0], defn[1]) in self.always_fix:
                self.definitions.itemconfigure(i, {'bg': 'green'})
            elif (defn[0], defn[1]) in self.never_fix:
                self.definitions.itemconfigure(i, {'bg': 'red'})

    def gather_defined_terms(self):

        terms = []
        for _, notice in self.trees.items():
            terms.extend(notice.defined_terms)

        terms.sort(key=itemgetter(0))
        return terms

    def scan_current_node_for_terms(self, event=None):

        node_text = self.xml_text.get('1.0', tk.END)
        label = self.current_node.get('label')
        self.terms = []
        self.unmarked_defs.delete(0, tk.END)

        for term, def_label, _ in self.gather_defined_terms():
            term_locations = set(find_all_occurrences(node_text, term))
            plural_term = self.inf.plural(term)
            plural_term_locations = set(find_all_occurrences(node_text, plural_term))
            unmarked_locs = list(plural_term_locations | term_locations ^ plural_term_locations)
            for start in unmarked_locs:
                if start in plural_term_locations:
                    term_to_use = plural_term
                elif start in term_locations:
                    term_to_use = term
                end = start + len(term_to_use)
                start_index = '1.0 + {} chars'.format(start)
                end_index = '1.0 + {} chars'.format(end)

                if not enclosed_in_tag(node_text, 'ref', start) and \
                        not enclosed_in_tag(node_text, 'def', start) and \
                        not enclosed_in_tag(node_text, 'title', start) and \
                        not enclosed_in_tag(node_text, 'subject', start):
                    term_data = (term_to_use, start, end, start_index, end_index, def_label)
                    if term_data not in self.terms:
                        self.terms.append(term_data)

        self.terms.sort(key=itemgetter(2))
        for term in self.terms:
            self.unmarked_defs.insert(tk.END, '{} [{}]'.format(term[0], term[1]))
            self.xml_text.tag_add('undefined_term', term[3], term[4])

        self.xml_text.tag_configure('undefined_term', background='yellow')

    def keypress_dispatcher(self, event):

        print event.keysym

    def terms_context_menu(self, event):

        def mark_always_fix():

            selection = self.definitions.curselection()
            for item in selection:
                term_split = self.definitions.get(item).split(':')
                term = (term_split[0], term_split[1].split()[0].strip())
                if term in self.always_fix:
                    self.definitions.itemconfigure(item, {'bg': 'white'})
                    try:
                        self.always_fix.remove(term)
                    except:
                        pass
                else:
                    self.definitions.itemconfigure(item, {'bg': 'green'})
                    self.always_fix.add(term)
                    try:
                        self.never_fix.remove(term)
                    except:
                        pass

        def mark_always_ignore():

            selection = self.definitions.curselection()
            for item in selection:
                term_split = self.definitions.get(item).split(':')
                term = (term_split[0], term_split[1].split()[0].strip())
                if term in self.never_fix:
                    self.definitions.itemconfigure(selection, {'bg': 'white'})
                    try:
                        self.never_fix.remove(term)
                    except:
                        pass
                else:
                    self.definitions.itemconfigure(selection, {'bg': 'red'})
                    self.never_fix.add(term)
                    try:
                        self.always_fix.remove(term)
                    except:
                        pass

        menu = tk.Menu(self.master, tearoff=0)
        menu.add_command(label='Always fix', command=mark_always_fix)
        menu.add_command(label='Never fix', command=mark_always_ignore)
        menu.post(event.x_root, event.y_root)

    def fix_selected_refs(self, event=None):

        offsets_and_values = []
        selections = self.unmarked_defs.curselection()
        for index in range(self.unmarked_defs.size()):
            term = self.terms[index]
            if (index in selections or (term[0], term[5]) in self.always_fix) and \
                    not (term[0], term[5]) in self.never_fix:
                ref = '<ref target="{}" reftype="term">{}</ref>'.format(term[5], term[0])
                offsets_and_values.append((ref, [term[1], term[2]]))

        node_text = self.xml_text.get('1.0', tk.END)
        if offsets_and_values:
            offsets_and_values = sorted(offsets_and_values, key=lambda x: x[1][0])
            values, offsets = zip(*offsets_and_values)
            new_text = interpolate_string(node_text, offsets, values)

            self.set_xml_text(new_text)
            new_element = etree.fromstring(new_text)
            self.current_node = new_element
            self.set_preview_text(new_element)
            self.trees[self.current_notice].replace_node(new_element.get('label'), new_element)
            self.scan_current_node_for_terms()

    def highlight_selected_terms(self, event):
        selections = self.unmarked_defs.curselection()
        indices = range(0, self.unmarked_defs.size())
        for index in indices:
            term = self.terms[index]
            start_index, end_index = '1.0+{}c'.format(term[1]), '1.0+{}c'.format(term[2])
            if index in selections:
                self.xml_text.tag_add('undefined_highlighted_term', start_index, end_index)
            else:
                self.xml_text.tag_remove('undefined_highlighted_term', start_index, end_index)
        self.xml_text.tag_configure('undefined_highlighted_term', background='red')
        self.xml_text.tag_raise('undefined_highlighted_term')

    def focus_on_term(self, event):

        selection = self.unmarked_defs.curselection()[0]
        term = self.terms[selection]
        self.xml_text.yview(term[3])

if __name__ == '__main__':

    root = tk.Tk()
    root.title('Menubar')
    root.geometry("1280x1024+300+300")
    app = EregsApp(root)
    root.mainloop()