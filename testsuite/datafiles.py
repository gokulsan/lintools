"""
Location of data files for LINtools unit testing

Data are stored in the "data/" subdirectory
Use as :
from lintools.testsuite.datafiles import *

"""

__all__ = [
	"PDB","GRO",
	"XTC",
	"MOL2"
 
]

from pkg_resources import resource_filename

PDB = resource_filename(__name__,'data/4XP1.pdb')
MOL2 = resource_filename(__name__,'data/LDP.mol2')
# This should be the last line: clean up namespace
del resource_filename