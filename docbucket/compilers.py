import os
import threading
from tempfile import mktemp, mkdtemp
from subprocess import Popen

from django import forms
from django.conf import settings
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured

import tagging.forms

from .forms import PageSelector


devnull = open(os.devnull, 'w')


class DocumentCompiler(object):

    name = None
    extensions = []

    def compile_files(self, filenames):
        """ Compile files into a PDF.

        Returns an open file like object to the output PDF file.
        """

    @classmethod
    def get_form(cls, *args, **kwargs):
        kwargs['ext_filter'] = cls.extensions
        return CreateDocumentForm(*args, **kwargs)


class AssembleMixIn(object):

    """ A mix-in for DocumentCompiler providing an assemble method.
    """

    ASSEMBLE_CMD = '/usr/bin/gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=%(output)s %(inputs)s'

    def assemble(self, filenames):
        """ Assemble all provided PDF files into one.
        """

        complete_pdf_filename = mktemp(suffix='.pdf')
        opts = {'inputs': ' '.join(filenames), 'output': complete_pdf_filename}
        if Popen(self.ASSEMBLE_CMD % opts, shell=True, stdout=devnull, stderr=devnull).wait() != 0:
            raise RuntimeError('Error while assemble')
        return complete_pdf_filename


class OcrTiffCompiler(DocumentCompiler, AssembleMixIn):

    """ This DocumentCompiler transforms tiff files in a searchable PDF file.
    """

    name = 'Tiff (with OCR)'
    extensions = ['.tiff']

    HOCR_CMD = '/usr/bin/cuneiform -l fra -f hocr -o %(output)s %(input)s'
    HOCR2PDF_CMD = '/usr/bin/hocr2pdf -i %(input_img)s -o %(output)s < %(input_hocr)s'

    def compile_files(self, filenames):
        pdfs = []
        for filename in filenames:
            pdfs.append(self._ocr(filename))

        complete_pdf_filename = self.assemble(pdfs)

        return open(complete_pdf_filename)

    def _ocr(self, filename):
        hocr_filename = mktemp(suffix='.html')
        pdf_filename = mktemp(suffix='.pdf')

        # Launch hocr file creation:
        opts = {'input': filename, 'output': hocr_filename}
        if Popen(self.HOCR_CMD % opts, shell=True, stdout=devnull, stderr=devnull).wait() != 0:
            raise RuntimeError('Error while hocr')

        # Launch pdf creation:
        opts = {'input_img': filename, 'output': pdf_filename,
                'input_hocr': hocr_filename}
        if Popen(self.HOCR2PDF_CMD % opts, shell=True, stdout=devnull, stderr=devnull).wait() != 0:
            raise RuntimeError('Error while hocr2pdf')

        return pdf_filename


class OcrPdfCompiler(OcrTiffCompiler):

    """ This DocumentCompiler transforms image only PDF files into a searchable
        PDF file.
    """

    name = 'PDF (with OCR)'
    extensions = ['.pdf']

    CONVERT_CMD = '/usr/bin/gs -r320 -dNOPAUSE -dBATCH -sOutputFile=%(output)s -sDEVICE=tiff24nc %(input)s'

    def compile_files(self, filenames):
        tmp_dir = mkdtemp()
        for i, filename in enumerate(filenames):
            opts = {'input': filenames[0], 'output': os.path.join(tmp_dir, 'out_%06d_%%06d.tiff' % i)}
            if Popen(self.CONVERT_CMD % opts, shell=True, stdout=devnull, stderr=devnull).wait() != 0:
                raise RuntimeError('Error while converting PDF to tiff')

        tiff_filenames = sorted(os.path.join(tmp_dir, x) for x in os.listdir(tmp_dir))
        return super(OcrPdfCompiler, self).compile_files(tiff_filenames)


class PdfCompiler(DocumentCompiler, AssembleMixIn):

    """ This DocumentCompiler allow to import PDF files without any processing.
    """

    name = 'PDF'
    extensions = ['.pdf']

    def compile_files(self, filenames):
        complete_pdf_filename = self.assemble(filenames)
        return open(complete_pdf_filename)


def load_compilers():
    """ Load all compilers found in settings.py file.
    """

    tls = threading.local()

    # Get the compilers list from the cache (QUIRK):
    if hasattr(tls, 'compilers'):
        return tls.compilers

    compilers = {}

    for import_path in settings.COMPILERS:

        module, attr = import_path.rsplit('.', 1)
        try:
            mod = import_module(module)
        except ImportError, e:
            raise ImproperlyConfigured('Error importing module %s: "%s"' %
                                       (module, e))
        try:
            Compiler = getattr(mod, attr)
        except AttributeError:
            raise ImproperlyConfigured('Module "%s" does not define a "%s" '
                                       'class.' % (module, attr))
        if not issubclass(Compiler, DocumentCompiler):
            raise ImproperlyConfigured('Finder "%s" is not a subclass of "%s"' %
                                       (Compiler, DocumentCompiler))
        compilers[Compiler.__name__.lower()] = Compiler

    tls.compilers = compilers

    return compilers


def compilers_processor(request):
    """ Context Processor used to get the list of document compilers.
    """

    compilers = load_compilers()
    return {'COMPILERS': [(k, v.name) for k, v in compilers.iteritems()]}


def list_incomings(ext_filter=None):
    """ Return the all the relevant files contained in incoming directory.
    """

    indir = settings.INCOMING_DIRECTORY

    files = ((f, f) for f
             in os.listdir(settings.INCOMING_DIRECTORY)
             if os.path.isfile(os.path.join(indir, f))
             and (ext_filter is None or os.path.splitext(f)[1] in ext_filter))

    return tuple(files)


class CreateDocumentForm(forms.Form):

    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'span8'}))
    tags = tagging.forms.TagField(widget=forms.TextInput(attrs={'class': 'span6'}), required=False)
    pages = forms.MultipleChoiceField(choices=(), widget=PageSelector)

    def __init__(self, *args, **kwargs) :
        ext_filter = kwargs.pop('ext_filter')
        super(CreateDocumentForm, self) .__init__(*args, **kwargs)
        self.fields['pages'].choices = list_incomings(ext_filter=ext_filter)
