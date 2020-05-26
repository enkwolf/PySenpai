"""
The core module defines the basic framework for testing (parts of) Python
programs. It contains three different test functions for testing individual
functions, main programs, code snippets, and source code / documentary (static
testing). Pylint review can also be integrated into the test results. This
module also provides necessary preparation functions that prepare the student
module for testing.

In addition to test functions, the module also has default callbacks that
provide a reasonable default behavior for testing simple functions and 
programs. A number of convenience callbacks are also provided that can be used
to replace default behavior - these cover most common cases of complication in
validating test results.

Understanding the testing procedure is necessary when writing checking programs
- especially in case of more complex tests. The testing procedure and optional 
arguments that are outlined in each testing function should help you understand
how information flows throughout the test and where and with what information 
your callbacks will be called.

Tool functions in this module can be used to perform certain tasks that are 
often needed in checkers.
"""

import argparse
import atexit
import copy
import importlib
import inspect
import io
import json
import os
import re
import sys

from stdlib_list import stdlib_list
from pylint import lint

INCORRECT = 0
CORRECT = 1
INFO = 2
ERROR = 3
DEBUG = 4
LINT_C = 10 #10
LINT_R = 11 #11
LINT_W = 12 #12
LINT_E = 13 #13

FNAME_PAT = re.compile("[a-zA-Z0-9_]+")


class JsonOutput(dict):
    """
    This class represents the JSON output of PySenpai. It is a dictionary with
    some added convenience methods for manipulating the inner data structures
    which would otherwise get out of hand with all the indexing and keying. It
    is only managed internally - checkers should not meddle with it. However, 
    should you really feel the need to, the internal output object can be 
    accessed as test_core.json_output.
    
    The JSON document created by this function matches the specification for
    the Lovelace learning environment's exercise evaluation format.
    """
    
    
    def __init__(self):
        super().__init__(self)
        self.__setitem__("tester", "")
        self.__setitem__("tests", [])
        
    def set_tester(self, name):
        """
        Sets the tester field of the JSON document. Usually this is called by 
        :func:`~test_core.set_tester` if you need to set it. The field is not
        currently required.
        """
        
        self.__setitem__("tester", name)
        
    def new_test(self, title):
        """
        This is called when a new test begins, i.e. when one of the test 
        functions (including load module) are called. It starts a new test
        structure in the JSON document with *title* as its title that will be
        shown in the output.
        """
        
        self.__getitem__("tests").append({
            "title": title,
            "runs": []
        })
        
    def new_run(self):
        """
        This is called when a new test case begins. There is no title, it 
        simply indicates that a new run structure should be started in the JSON
        document.
        """
        
        self.__getitem__("tests")[-1]["runs"].append({
            "output": []
        })
        
    def new_msg(self, content, flag, triggers=[], hints=[]):
        """
        Adds a new message to the test case output where *content* is the 
        actual message to be shown in the test log and *flag* is its category.
        A message can also include a list *triggers* that and *hints*. These 
        are explained in more detail under :ref:`output-messages`. 
        """
        
        self.__getitem__("tests")[-1]["runs"][-1]["output"].append({
            "msg": content,
            "flag": flag,
            "triggers": triggers,
            "hints": hints
        })
        
    def grind_params(self, template, var_names, values, question):
        """
        Adds grind parameters to the output. These are used only when the checker
        is a grind type checker and is used to generate a new task instance. 
        """
        
        self.__setitem__("grind_params", 
            {
                "template": template,
                "variables": var_names,
                "values": values, 
                "question": question
            }
        )
            
    def wrap_to(self, wrapper_dict, keyname):
        """
        Puts the evaluation dictionary inside another dictionary, using the
        specified *keyname*. The object then assumes the contents of
        *wrapper_dict* as its own. This method is used for routine type
        exercises that need to provided more context information than just the
        evaluation report.
        
        The reason this method is needed is the automatic output of the json
        report when this module exits. Therefore the output of the checker must
        always be contained in this module's internal dictionary - it cannot
        print its own output.
        """
    
        wrapper_dict[keyname] = self.copy()
        self.clear()
        self.update(wrapper_dict)

json_output = JsonOutput()

def find_first(pattern, string, rtype=str):
    """
    find_first(pattern, string[, rtype=str]) -> value
    
    Find the first match in *string* using compiled regular expression *pattern*. 
    If found, the match is converted into *rtype* before it's returned. If not found,
    returns None.    
    """
    
    try:
        return rtype(pattern.findall(string)[0])
    except IndexError:
        return None

def find_objects(st_module, object_type, first=True, name_only=False):
    """
    find_objects(st_module, object_type[, first=True][, name_only=False]) -> string or list
    
    Finds object(s) that are instance of the given type from the student code
    module. If *first* is True, only returns one object (list otherwise) and if
    *name_only* is True, returns name of the object (which can be used with
    setattr to assign a new value to the same name).
    
    This utility function is useful for exercises where checker needs to access
    a member of the student's code module, but its name has not been specified
    in the assignment. 
    """
    
    matches = []
    
    for name in dir(st_module):
        if not name.startswith("_"):
            if isinstance(getattr(st_module, name), object_type):
                if first:
                    if name_only:
                        return name
                    else:
                        return getattr(st_module, name)
                else:
                    if name_only:
                        matches.append(name)
                    else:
                        matches.append(getattr(st_module, name))
    else:
        if matches:
            return matches
        else:
            raise NoMatchingObject


class OutputParseError(Exception):
    """
    This exception should be raised by :ref:`output parsers <output-parsers>` if
    they fail to parse the student code's output properly.  This exception is
    handled in :func:`~test_core.test_function` and will result in:
    
    * the parsed result set to None
    * output of OutputParseError message with INCORRECT flag
    * output of OutputPatternInfo message with INFO flag    

    When raising *reason* can be given as additional information provided about
    the problem. The reason string is available as a keyword argument for format
    specifiers inside the OutputParseError message.
    """
    
    msg = ""

    def __init__(self, reason=""):
        super().__init__(self)
        self.msg = reason
        
    def __str__(self):
        return self.msg


class NoAdditionalInfo(Exception):
    """
    This exception should be raised by 
    :ref:`additional information functions <info-functions>` if they come to the
    conclusion that there is in fact no additional information that they can 
    give. It prevents the info function's message from being shown in the output. 
    """
    
    pass

class NoMatchingObject(Exception):
    """
    Raised by :func:`~test_core.find_objects` when it's unable to find objects
    of the specified type.
    """
    
    pass



class StringOutput(object):
    """
    This class is used as a replacement for sys.stdout whenever the student code
    is running. It saves the output into a string so that it can be parsed and/or 
    evaluated in the evaluation phase of the test. 
    """    
    
    errors = ""
    encoding = "utf-8"
    
    def __init__(self):
        self.content = ""
    
    def write(self, text):
        """
        Write into the contained string.
        """
        
        self.content += text        
        
    def clear(self):
        """
        Clear the contained string.
        """
        
        self.content = ""
        
    def flush(self):
        """
        Required to exist for file-like objects, doesn't need to do anything.
        """
        
        pass
        
        
class TranslationDict(dict):
    """
    This class is a customized dictionary that supports the multilingual support
    needed by PySenpai. Values are stored using two-part keys: keyword and
    language. Internally the keys are represented as strings in the form of
    :code:`"keyword:language"`.
    Three convenience methods are provided for storing and reading values from
    the dictionary.
    
    The core module comes with a set of predefined messages for each of test
    functions. When implementing checkers you can provide a TranslationDict
    object of your own which will be used to update the default dictionary for
    the test. See section :ref:`Output Messages <output-messages>` for more
    information.
    
    The class is usually used for output messages, but it is also handy for
    defining and retrieving regular expressions in multiple languages. 
    """   
    
    def set_msg(self, key, lang, value):
        """
        set_msg(key, lang, value)
        
        Sets a new *value* into the dictionary, forming a two-part key of *key* and *lang*.
        When using as a custom message dictionary, value can be either a string or a
        dictionary with up to three keys: content (str), hints (list) and triggers (list).
        If used internally within the checker, no limitations apply for value. However the
        update method only works with supported types of values.
        """
        
        self.__setitem__("{}:{}".format(key, lang), value)
        
    def get_msg(self, key, lang, default=None):
        """
        get_msg(key, lang[, default=None]) -> value
        
        Gets a value from the dictionary using *key* and *lang* to find the corresponding
        value. If the corresponding value is not found and *default* is set, another get 
        is performed using *default* and *lang* as the two-part key. If *default* is not 
        set or the corresponding value is not found, KeyError is raised.         
        """
        
        try:
            return self.__getitem__("{}:{}".format(key, lang))
        except KeyError:
            if default:
                return self.__getitem__("{}:{}".format(default, lang))
        raise KeyError
                
    def get_many(self, lang, *keys):
        """
        get_many(lang[, key1, ...]) -> list
        
        Gets multiple values from the dictionary and returns them as a list. Each *key* is 
        paired with *lang* to form the two-part keys. If any two-part key fails to match, a
        KeyError is raised.    
        """
        
        msgs = []
        for key in keys:
            msgs.append(self.get_msg(key, lang))
        return msgs
                
    def copy(self):
        """
        copy() -> TranslationDict
        
        Returns a copy.
        """
        
        return TranslationDict(self.items())
    
    def update(self, patch):
        """
        update(patch)
        
        Updates the dictionary from another TranslationDict instance. If a key already
        exists its value is updated by a) replacing its content value with the new value
        if the new value is a string; or b) running a normal dictionary update if it's a
        dictionary.
        
        If the key doesn't exist, it is added. The value is always a dictionary - if the
        given value is a string a dictionary is created and the string is placed into the
        content field.
        """
        
        for key, value in patch.items():
            try:
                if isinstance(value, str):
                    self.__getitem__(key)["content"] = value
                elif isinstance(value, dict):
                    self.__getitem__(key).update(value)
                else:
                    raise TypeError("Message must be str or dict")
            except KeyError:
                if isinstance(value, str):
                    self.__setitem__(key, {"content": value})
                else:
                    self.__setitem__(key, value)

                    
## Default messages ##

default_import_msgs = dim = TranslationDict()
default_program_test_msgs = dptm = TranslationDict()
default_func_test_msgs = dftm = TranslationDict()
default_code_snippet_test_msgs = dctm = TranslationDict()
default_static_test_msgs = dstm = TranslationDict()
default_lint_test_msgs = dltm = TranslationDict()

# ENGLISH DEFAULT MESSAGES
dim.set_msg("LoadingModule", "en", dict(content="Loading module {name} for evaluation..."))
dim.set_msg("GenericErrorMsg", "en", dict(content="An error occurred while importing the module.\n{ename}: {emsg}"))
dim.set_msg("PrintExcLine", "en", dict(content="Caused by line {lineno}:\n{{{{{{{line}}}}}}}"))
dim.set_msg("PrintInputVector", "en", dict(content="While using inputs:\n{inputs}"))
dim.set_msg("PrintStudentOutput", "en", dict(content="Your program's output while loading:\n{output}"))
dim.set_msg("MissingFileExtension", "en", dict(content="The file is missing the .py extension, which is required of Python code files."))
dim.set_msg("BadModuleName", "en", dict(content="The filename contained unsupported characters.\nOnly letters of the English alphabet, numbers and underscore are allowed."))
dim.set_msg("SystemModuleName", "en", dict(content="The filename {name} collides with a system module. Rename your file."))
dim.set_msg("ImportError", "en", dict(content="The code file was not found or imports inside it caused an ImportError.\nAdditional information:\n{emsg}"))
dim.set_msg("EOFError", "en", dict(content="An EOFError occurred while importing the module. The most likely cause is calling input too many times.\nAdditional information:\n{emsg}"))
dim.set_msg("SystemExit", "en", dict(content="The program was terminated through the use of:\nquit(), exit(), sys.exit(), raise SystemExit (etc.)\nYour program needs to be implemented such a way that it doesn't need any of these."))
dim.set_msg("SyntaxError", "en", dict(content="Your code included syntax errors. Do not use the checking program as a Python interpreter!\nYou should find all the errors in your code by running it in a shell as it provides more accurate information of what went wrong.\nSubmit your code for testing only after it runs on your computer!"))
dim.set_msg("IndentationError", "en", dict(content="Your code included indentation errors. Do not use the checking program as a Python interpreter!\nYou should find all the errors in your code by running it in a shell as it provides more accurate information of what went wrong.\nSubmit your code for testing only after it runs on your computer!"))
dim.set_msg("NameError", "en", dict(content="Your program contains an execution path that tries to access an undefined variable.\nAdditional information:\n{emsg}"))
dim.set_msg("DisallowedOutput", "en", dict(content="Your main program produced output, even though it's been specifically unallowed for this assignment. Please make sure your program doesn't execute extra code when being imported. Here is your program's output:\n{output}"))

dftm.set_msg("FunctionName", "en", dict(content="Testing function {name}..."))
dftm.set_msg("GenericErrorMsg", "en", dict(content="An error occurred while calling the function.\nAdditional information:\n{ename}: {emsg}\nTest the function on your computer to get more information."))
dftm.set_msg("TypeError", "en", dict(content="The function expects an incorrect number of arguments. Alternatively another kind of TypeError occurred while calling the function.\nAdditional information:\n{emsg}"))
dftm.set_msg("AttributeError", "en", dict(content="The function was not found, or another kind of AttributeError occurred while calling the function.\nAdditional information:\n{emsg}"))
dftm.set_msg("EOFError", "en", dict(content="An EOFError occurred while calling the function. The most likely cause is calling input too many times.\nAdditional information:\n{emsg}"))
dftm.set_msg("SystemExit", "en", dict(content="The program was terminated through the use of:\nquit(), exit(), sys.exit(), raise SystemExit (etc.)\nYour program needs to be implemented such a way that it doesn't need any of these."))
dftm.set_msg("IsNotFunction", "en", dict(content="An object called {name} was found, but it was not a function.\nTake care to not overwrite the function with another value in your main program!"))
dftm.set_msg("OutputParseError", "en", dict(content="Parsing the function's output for result values was not successful.\nCheck that your function uses the specified formatting when printing.\nReason provided by the checker:{reason}"))
dftm.set_msg("OutputPatternInfo", "en", dict(content=""))
dftm.set_msg("CorrectResult", "en", dict(content="The function returned the correct value(s)"))
dftm.set_msg("IncorrectResult", "en", dict(content="The function returned incorrect value(s)"))
dftm.set_msg("PrintExcLine", "en", dict(content="Caused by line {lineno}:\n{{{{{{{line}}}}}}}"))
dftm.set_msg("PrintTestVector", "en", dict(content="Function call used:\n{call}"))
dftm.set_msg("PrintInputVector", "en", dict(content="Using inputs:\n{inputs}"))
dftm.set_msg("PrintStudentResult", "en", dict(content="Your function returned: {res}"))
dftm.set_msg("PrintReference", "en", dict(content="Expected result: {ref}"))
dftm.set_msg("PrintStudentOutput", "en", dict(content="Your function's output:\n{output}"))
dftm.set_msg("AdditionalTests", "en", dict(content="Performing additional tests that may suggest cause for the error..."))
dftm.set_msg("AdditionalInfo", "en", dict(content="The checker gave the following as additional information:"))
dftm.set_msg("RepeatingResult", "en", dict(content="The function produced the same result twice in succession. This usually means the function is not reacting properly to arguments or inputs.\nThis is especially likely if this message pops up repeatedly."))
dftm.set_msg("CorrectMessage", "en", dict(content="The function's output was correct."))
dftm.set_msg("IncorrectMessage", "en", dict(content="The function's output was incorrect."))
dftm.set_msg("MessageInfo", "en", dict(content=""))

dptm.set_msg("ProgramName", "en", dict(content="Testing program..."))
dptm.set_msg("GenericErrorMsg", "en", dict(content="An error occurred while running the program.\nAdditional information:\n{ename}: {emsg}\nTest the program on your computer to get more information."))
dptm.set_msg("EOFError", "en", dict(content="The program prompted for more inputs than were provided by the tester. This is likely caused by faulty end condition handling.\nAdditional information:\n{emsg}"))
dptm.set_msg("ValueError", "en", dict(content="A ValueError occurred while running the program. This is likely caused by faulty handling of erroneous inputs.\nAdditional information:\n{emsg}"))
dptm.set_msg("TypeError", "en", dict(content="A TypeError occurred while running the program. This can be the result of not converting user inputs into proper types (inputs are always strings).\nAdditional information:\n{emsg}"))
dptm.set_msg("IndexError", "en", dict(content="An IndexError occurred while running the program. This can be caused by improper handling of split inputs, i.e. failing to check that the input contained enough parameters using the correct separator.\nAdditional information:\n{emsg}"))
dptm.set_msg("SystemExit", "en", dict(content="The program was terminated through the use of:\nquit(), exit(), sys.exit(), raise SystemExit (etc.)\nYour program needs to be implemented such a way that it doesn't need any of these."))
dptm.set_msg("OutputParseError", "en", dict(content="Parsing the program's output for result values was not successful.\nCheck that your program uses the specified formatting when printing.\nReason provided by the checker:{reason}"))
dptm.set_msg("OutputPatternInfo", "en", dict(content=""))
dptm.set_msg("CorrectResult", "en", dict(content="The program performed correctly."))
dptm.set_msg("IncorrectResult", "en", dict(content="The program's output contained incorrect results."))
dptm.set_msg("PrintExcLine", "en", dict(content="Caused by line {lineno}:\n{{{{{{{line}}}}}}}"))
dptm.set_msg("PrintInputVector", "en", dict(content="Using inputs:\n{inputs}"))
dptm.set_msg("PrintStudentResult", "en", dict(content="The following values were parsed from your program's output:\n{parsed}"))
dptm.set_msg("PrintReference", "en", dict(content="Expected to find these values:\n{ref}"))
dptm.set_msg("PrintStudentOutput", "en", dict(content="Your program's output:\n{output}"))
dptm.set_msg("AdditionalTests", "en", dict(content="Performing additional tests that may suggest cause for the error..."))
dptm.set_msg("AdditionalInfo", "en", dict(content="The checker gave the following as additional information:"))
dptm.set_msg("RepeatingResult", "en", dict(content="The program produced the same result twice in succession. This usually means the program is not reacting properly to inputs.\nThis is especially likely if this message pops up repeatedly."))
dptm.set_msg("CorrectMessage", "en", dict(content="The program's output was correct."))
dptm.set_msg("IncorrectMessage", "en", dict(content="The program's output was incorrect."))
dptm.set_msg("MessageInfo", "en", dict(content=""))

dctm.set_msg("SnippetTest", "en", dict(content="Testing code snippet..."))
dctm.set_msg("GenericErrorMsg", "en", dict(content="An error occurred while running the program.\nAdditional information:\n{ename}: {emsg}\nTest the code on your computer to get more information."))
dctm.set_msg("OutputParseError", "en", dict(content="Parsing the program's output for result values was not successful.\nCheck that your program uses the specified formatting when printing.\nReason provided by the checker:{reason}"))
dctm.set_msg("OutputPatternInfo", "en", dict(content=""))
dctm.set_msg("CorrectResult", "en", dict(content="The code performed correctly."))
dctm.set_msg("IncorrectResult", "en", dict(content="The code performed incorrectly."))
dctm.set_msg("PrintInputVector", "en", dict(content="While using inputs:\n{inputs}"))
dctm.set_msg("PrintStudentResult", "en", dict(content="Variables after execution:\n{res}"))
dctm.set_msg("PrintReference", "en", dict(content="Expected variables:\n{ref}"))
dctm.set_msg("PrintStudentOutput", "en", dict(content="Code output:\n{output}"))
dctm.set_msg("AdditionalTests", "en", dict(content="Performing additional tests that may suggest cause for the error..."))
dctm.set_msg("AdditionalInfo", "en", dict(content="The checker gave the following as additional information:"))
dctm.set_msg("CorrectMessage", "en", dict(content="The code's output was correct."))
dctm.set_msg("IncorrectMessage", "en", dict(content="The code's output was incorrect."))
dctm.set_msg("MessageInfo", "en", dict(content=""))
dctm.set_msg("fail_missing_variable", "fi", dict(content="The code didn't create a requested variable."))
dctm.set_msg("fail_variable_value", "fi", dict(content="The code assigned an incorrect value to a variable."))

dstm.set_msg("GenericErrorMsg", "en", dict(content="Something went wrong while reading the source code.\nAddional information:\n{ename}: {emsg}"))
dstm.set_msg("StaticTestInfo", "en", dict(content="Looking for potential problems in the source code..."))
dstm.set_msg("StaticTest", "en", dict(content="Checking the source code for violations of restrictions set by the assignment..."))
dstm.set_msg("AttributeError", "en", dict(content="A function called {fname} was not found from your code file."))
dstm.set_msg("OSError", "en", dict(content="Failed to read the source code."))
dstm.set_msg("CorrectResult", "en", dict(content="No problems were found in the source code."))

dltm.set_msg("LintTest", "en", dict(content="Testing code quality..."))
dltm.set_msg("GenericErrorMsg", "en", dict(content="Running the test failed.\nAdditional information:\n{ename}: {emsg}."))
dltm.set_msg("LintError", "en", dict(content="There were problems while running the test. Error output:\n{stderr}"))
dltm.set_msg("LintFailMessage", "en", dict(content="Your code didn't pass the quality test."))
dltm.set_msg("LintSuccess", "en", dict(content="Your code passed the quality check with score {global_note:.1f} / 10.0."))
dltm.set_msg("LintMessagesBegin", "en", dict(content="Problems found in the code are listed below."))
dltm.set_msg("LintMessage", "en", dict(content="The checker notified about line {line}. Explanation:\n{message}"))
dltm.set_msg("LintConvention", "en", dict(content="Convention violation at {module}, line {line}. Explanation:\n{message}"))
dltm.set_msg("LintRefactor", "en", dict(content="Bad code at {module}, line {line}. Explanation:\n{message}"))
dltm.set_msg("LintWarning", "en", dict(content="Potential problem at {module}, line {line}. Explanation:\n{message}"))
dltm.set_msg("LintError", "en", dict(content="Probable problem at {module}, line {line}. Explanation:\n{message}"))
dltm.set_msg("LintFatal", "en", dict(content="Unable to continue after {module}, line {line}. Explanation:\n{message}"))
dltm.set_msg("pylint_fail_low_score", "en", dict(content="Your code received too low quality score ({global_note:.1f} / 10.0).\nTarget: 5+ / 10.0."))



# FINNISH DEFAULT MESSAGES
dim.set_msg("LoadingModule", "fi", dict(content="Ladataan moduuli {name} arvioitavaksi..."))
dim.set_msg("GenericErrorMsg", "fi", dict(content="Ohjelmaa ladattaessa tapahtui poikkeus.\n{ename}: {emsg}"))
dim.set_msg("PrintExcLine", "fi", dict(content="Aiheutui rivistä {lineno}:\n{{{{{{{line}}}}}}}"))
dim.set_msg("PrintInputVector", "fi", dict(content="Käytettiin syötteitä:\n{inputs}"))
dim.set_msg("PrintStudentOutput", "fi", dict(content="Ohjelmasi tuloste ladatessa:\n{output}"))
dim.set_msg("MissingFileExtension", "fi", dict(content="Tiedostosta puuttuu .py-pääte, joka tulisi olla kaikissa Python-tiedostoissa."))
dim.set_msg("BadModuleName", "fi", dict(content="Tiedoston nimessä oli merkkejä joiden takia tarkistin ei pysty sitä avaamaan. Käytä vain englanninkielisiä aakkosia, numeroita ja alaviivaa nimessä."))
dim.set_msg("SystemModuleName", "fi", dict(content="Palautetun moduulin nimi {name} on sama kuin järjestelmämoduulin. Vaihda tiedoston nimi."))
dim.set_msg("ImportError", "fi", dict(content="Ohjelmaa ei löytynyt tai sen lataamisessa tapahtui ImportError.\nLisätietoja:\n{emsg}"))
dim.set_msg("EOFError", "fi", dict(content="Ohjelman suorituksessa tapahtui EOFError. Todennäköisin syy on input-funktion kutsuminen liian monta kertaa.\nLisätietoja:\n{emsg}"))
dim.set_msg("SystemExit", "fi", dict(content="Koodin suoritus on lopetettu väärin käyttämällä jotain seuraavista:\nquit(), exit(), sys.exit(), raise SystemExit\nToteuta ohjelma siten, että näille tai vastaaville keinoille ei ole tarvetta!"))
dim.set_msg("SyntaxError", "fi", dict(content="Koodi sisälsi syntaksivirheitä. Älä käytä tarkistusta Python-tulkkina!\nKorjaa koodisi virheet omalla koneella suorittamalla, jolloin saat tarkkaa tietoa missä ja millaisia virheet ovat.\nPalauta koodisi vasta kun saat sen komentorivillä toimimaan alusta loppuun!"))
dim.set_msg("IndentationError", "fi", dict(content="Koodi sisälsi sisennysvirheitä. Älä käytä tarkistusta Python-tulkkina!\nKorjaa koodisi virheet omalla koneella suorittamalla, jolloin saat tarkkaa tietoa missä ja millaisia virheet ovat.\nPalauta koodisi vasta kun saat sen komentorivillä toimimaan alusta loppuun!"))
dim.set_msg("NameError", "en", dict(content="Ohjelmassa on suorituspolku, jossa luetaan muuttujaa jota ei ole vielä luotu\nLisätietoja:\n{emsg}"))
dim.set_msg("DisallowedOutput", "fi", dict(content="Pääohjelmasi tuotti tulosteita, vaikka sen ei pitäisi. Muista varmistaa, että ohjelmasi ei suorita ylimääräisiä koodiriviejä kun se importataan. Ohjelma tulosti seuraavaa:\n{output}"))

dftm.set_msg("FunctionName", "fi", dict(content="Testataan {name}-funktiota..."))
dftm.set_msg("GenericErrorMsg", "fi", dict(content="Funktiota kutsuttaessa tapahtui poikkeus.\nLisätietoja:\n{ename}: {emsg}.\nTestaa funktiota omalla koneellasi saadaksesi lisätietoja."))
dftm.set_msg("TypeError", "fi", dict(content="Funktiolle on määritelty väärä määrä parametreja, tai sitä kutsuttaessa tapahtui jokin muu TypeError.\nTarkista tehtävänannosta millaset parametrit funktiolla tulisi olla\nLisätietoja:\n{emsg}"))
dftm.set_msg("AttributeError", "fi", dict(content="Oikean nimistä funktiota ei löytynyt, tai sitä kutsuttaessa tapahtui jokin muu AttributeError.\nLisätietoja:\n{emsg}"))
dftm.set_msg("EOFError", "fi", dict(content="Funktio pyysi enemmän syötteitä kuin testausohjelma antoi. Tämä voi johtua väärin käsitellystä funktion lopetusehdosta.\nLisätietoja:\n{emsg}"))
dftm.set_msg("SystemExit", "fi", dict(content="Koodin suoritus on lopetettu väärin käyttämällä jotain seuraavista:\nquit(), exit(), sys.exit(), raise SystemExit\nToteuta ohjelma siten, että näille tai vastaaville keinoille ei ole tarvetta!"))
dftm.set_msg("IsNotFunction", "fi", dict(content="Objekti nimeltä {name} löytyi, mutta se ei ollut funktio.\nVarmista, että olet käyttänyt oikeaa funktion nimeä, ja että funktion päälle ei pääohjelmassa kirjoiteta jotain muuta samalla nimellä."))
dftm.set_msg("OutputParseError", "fi", dict(content="Funktion tulosteesta ei löytynyt kaikkia arvoja.\nVarmista että käytät tehtävänannossa määriteltyä muotoilua tulosteille.\nEpäonnistumisen syy: {reason}"))
dftm.set_msg("OutputPatternInfo", "fi", dict(content=""))
dftm.set_msg("CorrectResult", "fi", dict(content="Funktio palautti oikean tuloksen."))
dftm.set_msg("IncorrectResult", "fi", dict(content="Funktio palautti väärän tuloksen."))
dftm.set_msg("PrintExcLine", "fi", dict(content="Aiheutui rivistä {lineno}:\n{{{{{{{line}}}}}}}"))
dftm.set_msg("PrintTestVector", "fi", dict(content="Käytetty funktiokutsu:\n{call}"))
dftm.set_msg("PrintInputVector", "fi", dict(content="Kokeiltiin syötteillä:\n{inputs}"))
dftm.set_msg("PrintStudentResult", "fi", dict(content="Funktio palautti: {res}"))
dftm.set_msg("PrintReference", "fi", dict(content="Olisi pitänyt palauttaa: {ref}"))
dftm.set_msg("PrintStudentOutput", "fi", dict(content="Funktiosi koko tuloste:\n{output}"))
dftm.set_msg("AdditionalTests", "fi", dict(content="Suoritetaan lisätestejä, jotka saattavat kertoa mistä virhe johtuu..."))
dftm.set_msg("AdditionalInfo", "fi", dict(content="Tarkistin antoi myös seuraavat lisätiedot:"))
dftm.set_msg("RepeatingResult", "fi", dict(content="Funktio tuotti kahdesti peräkkäin saman tuloksen. Tämä yleensä tarkoittaa, että funktio ei reagoi odotetulla tavalla sille annettuihin argumentteihin tai syötteisiin.\nTämä pätee erityisesti jos tämä viesti toistuu."))
dftm.set_msg("CorrectMessage", "fi", dict(content="Funktion tulosteet olivat oikein."))
dftm.set_msg("IncorrectMessage", "fi", dict(content="Funktion tuloste oli virheellinen."))
dftm.set_msg("MessageInfo", "fi", dict(content=""))

dptm.set_msg("ProgramName", "fi", dict(content="Testataan ohjelmaa..."))
dptm.set_msg("GenericErrorMsg", "fi", dict(content="Ohjelmaa suorittaessa tapahtui poikkeus.\nLisätietoja:\n{ename}: {emsg}\nTestaa ohjelmaa omalla koneellasi saadaksesi lisätietoja."))
dptm.set_msg("EOFError", "fi", dict(content="Ohjelma pyysi enemmän syötteitä kuin testausohjelma antoi. Tämä voi johtua väärin käsitellystä ohjelman lopetusehdosta. Lisätietoja:\n{emsg}"))
dptm.set_msg("ValueError", "fi", dict(content="Ohjelmaa suorittaessa tapahtui ValueError. Tämä voi johtua siitä, että virheellisiä syötteitä ei ole käsitelty oikein.\nLisätietoja:\n{emsg}"))
dptm.set_msg("TypeError", "fi", dict(content="Ohjelmaa suorittaessa tapahtui TypeError. Tämä voi johtua siitä, että syötteitä ei muuteta ennen käyttöä (syötteet ovat aina merkkijonoja).\nLisätietoja:\n{emsg}"))
dptm.set_msg("IndexError", "fi", dict(content="Ohjelmaa suorittaessa tapahtui IndexError. Tämä voi johtua siitä, että ohjelma ei käsittele oikein moniosaisia syötteitä, joista puuttuu osia, tai joissa on väärä erotin.\nLisätietoja:\n{emsg}"))
dptm.set_msg("SystemExit", "fi", dict(content="Koodin suoritus on lopetettu väärin käyttämällä jotain seuraavista:\nquit(), exit(), sys.exit(), raise SystemExit\nToteuta ohjelma siten, että näille tai vastaaville keinoille ei ole tarvetta!"))
dptm.set_msg("OutputParseError", "fi", dict(content="Ohjelman tulosteesta ei löytynyt kaikkia arvoja.\nVarmista että käytät tehtävänannossa määriteltyä muotoilua tulosteille.\nEpäonnistumisen syy: {reason}"))
dptm.set_msg("OutputPatternInfo", "fi", dict(content=""))
dptm.set_msg("CorrectResult", "fi", dict(content="Ohjelma toimi oikein."))
dptm.set_msg("IncorrectResult", "fi", dict(content="Ohjelman tuloste sisälsi virheellisiä arvoja."))
dptm.set_msg("PrintExcLine", "fi", dict(content="Aiheutui rivistä {lineno}:\n{{{{{{{line}}}}}}}"))
dptm.set_msg("PrintInputVector", "fi", dict(content="Käytettiin syötteitä:\n{inputs}"))
dptm.set_msg("PrintStudentResult", "fi", dict(content="Ohjelman tulosteesta löytyneet arvot:\n{parsed}"))
dptm.set_msg("PrintReference", "fi", dict(content="Arvot joiden olisi pitänyt löytyä:\n{ref}"))
dptm.set_msg("PrintStudentOutput", "fi", dict(content="Ohjelmasi koko tuloste:\n{output}"))
dptm.set_msg("AdditionalTests", "fi", dict(content="Suoritetaan lisätestejä, jotka saattavat kertoa mistä virhe johtuu..."))
dptm.set_msg("AdditionalInfo", "fi", dict(content="Tarkistin antoi myös seuraavat lisätiedot:"))
dptm.set_msg("RepeatingResult", "fi", dict(content="Ohjelma tuotti kahdesti peräkkäin saman tuloksen. Tämä yleensä tarkoittaa, että ohjelma ei reagoi odotetulla tavalla sille annettuihin syötteisiin.\nTämä pätee erityisesti jos tämä viesti toistuu."))
dptm.set_msg("CorrectMessage", "fi", dict(content="Ohjelman tulosteet olivat oikein."))
dptm.set_msg("IncorrectMessage", "fi", dict(content="Ohjelman tuloste oli virheellinen."))
dptm.set_msg("MessageInfo", "fi", dict(content=""))

dctm.set_msg("SnippetTest", "fi", dict(content="Testataan koodipätkää..."))
dctm.set_msg("GenericErrorMsg", "fi", dict(content="Koodia suorittaessa tapahtui poikkeus.\nLisätietoja:\n{ename}: {emsg}\nTestaa koodia omalla koneellasi ohjeita seuraten saadaksesi lisätietoja."))
dctm.set_msg("OutputParseError", "fi", dict(content="Koodin tulosteesta ei löytynyt kaikkia arvoja.\nVarmista että käytät tehtävänannossa määriteltyä muotoilua tulosteille.\nEpäonnistumisen syy: {reason}"))
dctm.set_msg("OutputPatternInfo", "fi", dict(content=""))
dctm.set_msg("CorrectResult", "fi", dict(content="Koodi toimi oikein."))
dctm.set_msg("IncorrectResult", "fi", dict(content="Koodi toimi väärin."))
dctm.set_msg("PrintInputVector", "fi", dict(content="Käytettiin syötteitä:\n{inputs}"))
dctm.set_msg("PrintStudentResult", "fi", dict(content="Muuttujien arvot suorituksen jälkeen:\n{res}"))
dctm.set_msg("PrintReference", "fi", dict(content="Odotetut muuttujien arvot:\n{ref}"))
dctm.set_msg("PrintStudentOutput", "fi", dict(content="Koodin tuloste:\n{output}"))
dctm.set_msg("AdditionalTests", "fi", dict(content="Suoritetaan lisätestejä, jotka saattavat kertoa mistä virhe johtuu..."))
dctm.set_msg("AdditionalInfo", "fi", dict(content="Tarkistin antoi myös seuraavat lisätiedot:"))
dctm.set_msg("CorrectMessage", "fi", dict(content="Koodin tulosteet olivat oikein."))
dctm.set_msg("IncorrectMessage", "fi", dict(content="Koodin tuloste oli virheellinen."))
dctm.set_msg("MessageInfo", "fi", dict(content=""))
dctm.set_msg("fail_missing_variable", "fi", dict(content="Koodissa ei luotu pyydettyä muuttujaa."))
dctm.set_msg("fail_variable_value", "fi", dict(content="Koodi sijoitti muuttujaan väärän arvon."))


dstm.set_msg("GenericErrorMsg", "fi", dict(content="Jokin meni pieleen lähdekoodia luettaessa.\nLisätietoja:\n{ename}: {emsg}"))
dstm.set_msg("StaticTestInfo", "fi", dict(content="Etsitään koodista mahdollisia ongelmia..."))
dstm.set_msg("StaticTest", "fi", dict(content="Tarkistetaan noudattaako koodi tehtävänannon rajoituksia..."))
dstm.set_msg("AttributeError", "fi", dict(content="{fname}-nimistä funktiota ei löytynyt kooditiedostosta."))
dstm.set_msg("OSError", "fi", dict(content="Lähdekoodin lukeminen epäonnistui."))
dstm.set_msg("CorrectResult", "fi", dict(content="Koodista ei löytynyt ongelmia."))

dltm.set_msg("LintTest", "fi", dict(content="Tarkistetaan koodin laatua..."))
dltm.set_msg("GenericErrorMsg", "fi", dict(content="Testaus epäonnistui.\nLisätietoja:\n{ename}: {emsg}."))
dltm.set_msg("LintError", "fi", dict(content="Testin ajossa oli ongelmia. Virheviestit:\n{stderr}"))
dltm.set_msg("LintFailMessage", "fi", dict(content="Koodisi ei läpäissyt laatutarkistusta."))
dltm.set_msg("LintSuccess", "fi", dict(content="Koodisi läpäisi laatutarkistuksen pisteillä {global_note:.1f} / 10.0."))
dltm.set_msg("LintMessagesBegin", "fi", dict(content="Koodista löytyneet ongelmat on listattu alla."))
dltm.set_msg("LintMessage", "fi", dict(content="Tarkistin ilmoitti rivistä {line}. Selitys:\n{message}"))
dltm.set_msg("LintConvention", "fi", dict(content="Käytäntöjä rikkovaa koodia tiedostossa {module}, rivillä {line}. Selitys:\n{message} ({symbol})"))
dltm.set_msg("LintRefactor", "fi", dict(content="Huonolaatuista koodia tiedostossa {module}, rivillä {line}. Selitys:\n{message} ({symbol})"))
dltm.set_msg("LintWarning", "fi", dict(content="Mahdollinen ongelmien aiheuttaja tiedostossa {module}, rivillä {line}. Selitys:\n{message} ({symbol})"))
dltm.set_msg("LintError", "fi", dict(content="Todennäköinen ongelmien aiheuttajat tiedostossa {module}, rivillä {line}. Selitys:\n{message} ({symbol})"))
dltm.set_msg("LintFatal", "fi", dict(content="Tarkistuksen keskeyttänyt ongelma tiedostossa {module}, rivillä {line}. Selitys:\n{message} ({symbol})"))
dltm.set_msg("pylint_fail_low_score", "fi", dict(content="Koodisi sai liian pienet laatupisteet ({global_note:.1f} / 10.0).\nTavoite: 5+ / 10.0."))
dltm.set_msg("pylint_fail_low_score", "fi", dict(content="Koodisi sai liian pienet laatupisteet ({global_note:.1f} / 10.0).\nTavoite: 5+ / 10.0."))


## Default and convenience functions for various keyword arguments ##

class SimpleRef(object):
    """
    This object simulates a module for code snippet tests. When created,
    attributes can be set to be compared with the student module.
    """
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def __call__(self, inputs):        
        return self
        

def result_validator(ref, res, out):
    """
    This is the default validator function that provides reasonable validation
    for tests where the return values are either strings or integers, or 
    sequences containing similar simple types. The behavior provided by this 
    validator is direct comparison of values between the student result *res* and the
    reference result *ref*. 
    
    For convenience, string values are stripped of blanks before comparison and
    lists are converted to tuples. Sequence contents are not touched.
    """
    
    if isinstance(ref, str):
        ref = ref.strip()
    if isinstance(res, str):
        res = res.strip()
    if isinstance(ref, list):
        ref = tuple(ref)
    if isinstance(res, list):
        res = tuple(res)        
    assert res == ref
    
def rounding_float_result_validator(ref, res, out):
    """
    This is a convenience callback for validating functions that return floating
    point values. Values are rounded to two decimal precision in order to account 
    for precision error caused by different implementations. The function compares
    student result *res* against the reference result *ref*. 
    """
    
    if isinstance(res, float):
        assert round(res, 2) == round(ref, 2)
    else:
        raise AssertionError
    
def parsed_list_validator(ref, res, out):
    """
    This is a convenience callback for validating lists of parsed results against 
    a reference list. The comparison of *out* to *ref* is done item by item as opposed 
    to the default validator (which compares *res*). Comparison is done item to item.
    """
    
    try:
        for i, v in enumerate(ref):
            assert v == out[i]
    except IndexError:
        raise AssertionError
    
def parsed_result_validator(ref, res, out):
    """
    This is the default validator for program tests, and a convenience callback for
    validating functions that print simple values. It compares the values parsed from
    student output *out* to values returned by the reference function *ref*. 
    
    Similar to the default validator, strings are stripped of blanks before comparison
    and lists are converted to tuples. Sequence contents are not touched. 
    """
    
    if isinstance(ref, str):
        ref = ref.strip()
    if isinstance(out, str):
        out = out.strip()
    if isinstance(ref, list):
        ref = tuple(ref)
    if isinstance(out, list):
        out = tuple(out)        
    assert out == ref
 
def vars_validator(ref, res, out):
    """
    Default validator for code snippet tests. Compares variable names and values
    found within the executed student module and the reference object.
    """
    
    for name in ref.__dict__.keys():
        if not name.startswith("_"):
            assert hasattr(res, name), "fail_missing_variable"
            assert getattr(res, name) == getattr(ref, name), "fail_variable_value"
     
 
def default_pylint_validator(stats):
    """
    Default validator for pylint tests. Fails if score is less than 5. 
    """
    
    try:
        assert stats["global_note"] >= 5, "pylint_fail_low_score"
    except KeyError:
        raise AssertionError
 
 
# Old default presenter, preserved for backwards compatibility.
def default_presenter(value) -> str:
    """
    .. deprecated:: 0.5
    
    This is the old default default presenter. It presents *value* in a neater form for 
    output purposes. It returns single values as strings and formats lists, tuples and 
    dictionaries into more a readable presentation. 
    
    The function is preserved for legacy purposes - it being called as the default 
    behavior by some checkers' custom presenter callbacks. The single presenter function
    system has been replaced in 0.5 by presenter dictionaries. See section 
    :ref:`Presenters <presenters>` for more information.
    """
    
    if isinstance(value, (list, tuple)):
        return " ".join([str(x) for x in value])
    elif isinstance(value, dict):
        return "\n".join(["{}: {}".format(k, v) for k, v in value.items()])
    else:
        return value    
    
    
def default_value_presenter(value) -> str:
    """
    This is the default presenter for student result values, parsed results, reference values
    and function arguments. For simple values, repr is used to show the difference between 
    strings that are digits and actual numbers. One-dimensional lists and tuples are presented
    using repr for each invidual item and items are separated with spaces. Dictionary items are 
    presented as :code:`"{}: {}"` where repr of both key and value are used.    
    
    For more precise control of representing more complex structures, a custom presenter is
    recommended.
    """    
    
    if isinstance(value, (list, tuple)):
        return " ".join([repr(x) for x in value])
    elif isinstance(value, dict):
        return "\n".join(["{}: {}".format(repr(k), repr(v)) for k, v in value.items()])
    else:
        return repr(value)
    
def default_input_presenter(value) -> str:
    """
    This is the default presenter for input vectors. Individual inputs are separated by spaces
    and they are shown using str instead of repr. 
    """
    
    return "{{{\n" + "\n".join([str(x) for x in value]) + "\n}}}"
    
def default_call_presenter(func_name, args) -> str:
    """
    This function is used for showing the way the student function was called
    during a test. It forms a function call code line using the function name 
    and its arguments. If the call would be long (over 80 characters), it is 
    split to multiple lines. 
    """
    
    call = func_name + "("
    if len(str(args)) > 80:
        call += "\n"
        call += ",\n".join("    " + repr(arg) for arg in args)
        call += "\n)"
    else:
        call += ", ".join(repr(arg) for arg in args)
        call += ")"
    
    return "{{{highlight=python3\n" + call + "\n}}}"
    
    
def default_vars_presenter(module) -> str:
    """
    Default presenter for student module variables in code snippet tests. 
    """
    
    var_vals = ""
    for name in sorted(module.__dict__.keys()):
        if not name.startswith("_"):
            var_vals += "{} = {}\n".format(name, repr(getattr(module, name)))
        
    return var_vals
    
    
def raw_presenter(value) -> str:
    """
    This is the simplest presenter that simply returns the repr form of a *value*. 
    """
    
    return repr(value)
    
def default_parser(out) -> str:
    """
    This is a dummy output parser that is used as the default. It is usable in tests where
    output is not evaluated. 
    """
    
    return out
    
def default_message_validator(out, args, inputs):
    """
    This dummy validator is used as the default message validator. It is usable in tests where
    messages are not evaluated.
    """
    
    pass
    
def default_argument_cloner(args):
    """
    Dummy cloner to be used as the default. Used whenever there is no need to clone the 
    argument vector. 
    """
    
    return args

def default_new_test(args, inputs):
    """
    Default actions to take at the start of each individual test case. The default action is
    to do nothing.
    """
    
    pass

## Internal stuff ##
    
default_presenters = {
    "arg": default_value_presenter,
    "input": default_input_presenter, 
    "ref": default_value_presenter,
    "res": default_value_presenter,
    "parsed": default_value_presenter,
    "call": default_call_presenter,
    "vars": default_vars_presenter,
    "ref_vars": default_vars_presenter
}

# Output function. Change this to fit your environment if needed. 
    
def output(_msg, _flag, **_format_args):
    """
    Outputs message into the JSON document. Just a shorthand that makes the
    rest of the code look less messy.
    """
    
    if _msg["content"]:
        json_output.new_msg(
            _msg["content"].format(**_format_args), 
            _flag,
            _msg.get("triggers", []),
            _msg.get("hints", [])
        )
        
def reset_locals(module):
    """
    This function ensures that the student module is clean after each execution.
    It deletes all names from the *module*'s namespace. The reason for this procedure
    is that occasionally students return programs where all names are not set on 
    every run. When the code is run normally these scenarios would result in 
    UnboundLocalError. However, if the name was successfully set on the first run
    but is not set on the second run, the value from the first run is retained when
    using importlib.reload. This results in weird errors that are avoided when all 
    locals are nuked from the orbit before reloading the module. 
    """
    
    m_locals = [name for name in dir(module) if not name.startswith("__")]
    for name in m_locals:
        delattr(module, name)
    
def walk_trace(tb, tb_list):    
    """
    Turns the stack traceback into a list by recurring through it. 
    """
    
    tb_list.append(tb)
    if tb.tb_next:
        walk_trace(tb.tb_next, tb_list)

def get_exception_line(module, etrace):
    """
    This function goes through a traceback and finds the last line of code from 
    within *module* that was involved in causing the exception. This function 
    is used whenever there is an exception to show the student which line of 
    their code caused it. After getting the line number from the traceback, 
    the function finds the corresponding line from the student's code file and
    returns it alongside the line number.
    
    If no line is found, it returns ? for the line number and nothing for the 
    line itself - this usually occurs when the student's function definition 
    doesn't match the expected one, resulting in a TypeError. 
    """
    
    tb_list = []
    try:
        walk_trace(etrace, tb_list)
    except RecursionError:
        pass
    #for tb in tb_list:
    #    print(tb.tb_frame.f_code.co_filename)
    try:
        st_last_frame = [tb.tb_frame for tb in tb_list if tb.tb_frame.f_code.co_filename == module.__file__][-1]
    except IndexError:
        return "?", ""
        
    with open(module.__file__) as cf:
        for i in range(st_last_frame.f_lineno):
            code = cf.readline()
        return st_last_frame.f_lineno, code.strip()
        
## Actual test functions ##

def set_tester(name):
    """
    Sets the tester name. Call this is in the checker if you need the checker's
    file name included in the output JSON document.
    """
    
    json_output.set_tester(name)

class CommaSplitAction(argparse.Action):
    """
    Action class for argument parsing. Takes a comma separated string and
    returns the split result as integers. Used in routine exercise parsing with
    the argument that chooses question types to use.
    """
    
    def __call__(self, parser, namespace, values, options=None):
        setattr(namespace, self.dest, [int(v) for v in values.split(",")])


def parse_command():
    """
    parse_command() -> list, str
    
    This parses the checker command for files to test and testing language. Available
    arguments are:
    
    * -l --lang --locale : sets the checker language using language codes
    * -q --questions : enabled question types (integers) as comma-separated string
    * -c --check : check a routine exercise answer (and generate another)
    * -r --request : request new routine exercise instance
    
    Everything else is considered as files to test.

    Returns all files' basenames as a list and the language as a separate value.
    
    If the files are located in subfolders, adds the folders to the path. This makes them
    importable later.
    
    When writing checkers, this is typically the first function to call. 
    """
    
    parser = argparse.ArgumentParser()
    parser.add_argument("files", metavar="filename", nargs="*", help="file(s) to test")
    parser.add_argument(
        "-l", "--locale", "--lang",
        dest="lang",
        default="en",
        help="locale to use for running the test"
    )
    parser.add_argument(
        "-q" "--questions",
        action=CommaSplitAction,
        dest="questions",
        default="",
        help="list of comma separated question classes to choose from"
    )

    parser.add_argument(
        "-c", "--check", 
        action="store_const",
        dest="check",
        const=True,
        default=False,
        help="checking a grind session"
    )
    parser.add_argument(
        "-r", "--request-params", 
        action="store_const",
        dest="request",
        const=True,
        default=False,
        help="command is a request for params"
    )
    args = parser.parse_args()
    if args.request or args.check:
        with open(args.files[0]) as s:
            return json.load(s), args

    for i, path in enumerate(args.files):
        if os.path.dirname(path):
            sys.path.insert(0, os.path.dirname(path))
        #args.files[i] = os.path.basename(path)
    
    return args.files, args.lang    
    
    
    
# NOTE: custom_msgs, inputs are read only
# therefore setting defaults to empty lists / dictionaries is safe here. 
def load_module(module_path, 
                lang="en", 
                custom_msgs={}, 
                inputs=[], 
                hide_output=True, 
                allow_output=True, 
                presenter=default_input_presenter):
    """
    load_module(module_path[, lang="en"][, custom_msgs={}][, inputs=[]][, hide_output=True][, allow_output=True][, presenter=default_input_presenter]) -> Module
    
    This function imports the student module and needs to be called before doing tests.
    The parameters are
    
    * *lang* - language for messages
    * *custom_msgs* - a TranslationDict object that includes additions/overrides 
      to the default import messages
    * *inputs* - input vector to be given to the program; inputs are automatically joined 
      by newlines and made into a StringIO object that replaces standard input. When 
      calling this function you need to provide inputs that allow the program to execute
      without errors. 
    * *hide_output* - a flag to hide or show output, by default output is hidden
    * *allow_output* - a flag that dictates whether it's considered an error if the code
      has output or not. By default output is allowed.
    * *presenter* - a presenter function for showing inputs in the output in case of
      errors
       
    Before attempting to import the student module, the function checks whether the 
    filename is a proper Python module name. None is returned if the filename is
    invalid. This also happens if the module has the same name as a Python library module.
    
    If importing the student module results in an exception, the exception's name is
    looked up from the message dictionary and the corresponding error message is
    shown in the checker output. If the exception name is not found, GenericErrorMsg
    is shown instead. See :ref:`Output Messages <output-messages>` for information
    about how to specify your own error messages. 
    
    If importing is successful and *allow_output* is set to False, the StringOutput
    object is checked for prints and an error message is given if content is found.
    Otherwise the module object is returned.    
    """

    save = sys.stdout
    msgs = copy.deepcopy(default_import_msgs)
    msgs.update(custom_msgs)
    
    module_name = os.path.basename(module_path)
    
    json_output.new_test(msgs.get_msg("LoadingModule", lang)["content"].format(name=module_name))
    json_output.new_run()
    
    if not module_name.endswith(".py"):
        output(msgs.get_msg("MissingFileExtension", lang), ERROR)
        return None

    name = module_name.rsplit(".py", 1)[0]
    if not FNAME_PAT.fullmatch(name):    
        output(msgs.get_msg("BadModuleName", lang), ERROR, name=module_name)
        return None
        
    pyver = "{}.{}".format(sys.version_info.major, sys.version_info.minor)
        
    if name in stdlib_list(pyver):
        output(msgs.get_msg("SystemModuleName", lang), ERROR, name=module_name)
        return None
        
    if inputs:
        sys.stdin = io.StringIO("\n".join([str(i) for i in inputs]))
        
    o = StringOutput()
    sys.stdout = o
    
    try:        
        st_module = importlib.import_module(name)
    except:
        sys.stdout = save
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        #elineno, eline = get_exception_line(st_module, etrace)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, 
            ename=ename, emsg=emsg, inputs=presenter(inputs)
        )
        if inputs:
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=presenter(inputs))
    else:
        sys.stdout = save
        if not allow_output and o.content:
            output(msgs.get_msg("DisallowedOutput", lang), ERROR, output=o.content)
        elif not hide_output:
            output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=o.content)
            
        return st_module
    
    
# NOTE: custom_msgs, inputs, error_refs, custom_tests, info_funcs are read only
# therefore setting defaults to empty lists / dictionaries is safe here. 
def test_function(st_module, func_names, test_vector, ref_func,
                  lang="en",
                  custom_msgs={},
                  inputs=[],
                  hide_output=True,
                  test_recurrence=True,
                  ref_needs_inputs=False,
                  error_refs=[],
                  custom_tests=[],
                  info_funcs=[],
                  validator=result_validator,
                  presenter=default_presenters,
                  output_parser=default_parser,
                  message_validator=None,
                  result_object_extractor=None,
                  argument_cloner=default_argument_cloner,
                  repeat=1,
                  new_test=default_new_test): 
    """
    test_function(st_module, func_names, test_vector, ref_func[, lang="en"][, kwarg1][, ...])
    
    Tests a student function with a set of test vectors, against a reference 
    function. The behavior of this function can be customized heavily by using 
    callbacks and other optional keyword arguments. All arguments are listed and
    explained below. 
    
    * *st_module* - a module object that contains the function that's being tested
    * *func_names* - a dictionary that has two character language codes as keys and
      corresponding function name in that language as values
    * *test_vector* - a list of argument vectors or a function that generates the 
      the list. This vector must be sequences within a list, where each sequence 
      is one test case. Each case vector is unpacked when reference and student 
      functions are called.
    * *ref_func* - reference function that gets called with the same arguments as
      the student function to obtain the reference result for each test case.
    * *lang* - language for messages and for finding the student function
    * *custom_msgs* - a TranslationDict object that includes additions/overrides 
      to the default function test messages
    * *inputs* - input vectors to be given to the function; must have as many vectors 
      as test_vector. Inputs are automatically joined by newlines and made into a 
      StringIO object that replaces standard input. Necessary when testing functions 
      that accept user input.
    * *hide_output* - a flag to show/hide student function prints in the test 
      output. By default student output is hidden. 
    * *test_recurrence* - a flag to enable/disable a convenience test that checks
      if the student code repeatedly returns the same result regardless of 
      arguments/inputs given to the function. Default is True. Should be disabled
      for functions that don't return anything to avoid confusing messages.
    * *ref_needs_inputs* - if set to True, the reference function is given two 
      lists instead of unpacking the argument vector for each case. In this case 
      the reference function is always called with exactly two parameters: list of 
      arguments and list of inputs. Default is False. This behavior is necessary if
      your reference function needs to change its result based on inputs. 
    * *error_refs* - a list of false reference functions that will be called if the
      student function output does not match the true reference. These are useful
      for exposing common implementation errors. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *custom_tests* - a list of test functions that are called if the test is failed. 
      These tests can examine any of the test parameters and raise AssertionError if 
      problems are detected. See :ref:`Providing Debug Information <debug-information>` 
      for more about these functions. 
    * *info_funcs* - a list of information functions that are called if the test fails.
      These are similar to custom tests, but instead of making asserts, they should 
      return a value that is shown in the corresponding output message. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *validator* - the function that performs the validation of the student function
      return value and/or parsed output against the reference. Validators must use 
      assert. The assert's error message is used to retrieve a message from the 
      dictionary to show in the output as the test result in case of failure.
    * *presenter* - a dictionary with any or all of the following keys: arg, call,
      input, ref, res, parsed. Each key must be paired with a function that returns
      a string. These functions are used to make data structures cleaner in the output.
      See section :ref:`Presenters <presenters>` for more information.
    * *output_parser* - a function that retrieves data by parsing the student 
      function's output. Values obtained by the parser are offered separately from 
      the function's return values to the validator. Output parsers can abort the 
      test case by raising OutputParseError.
    * *message_validator* - a function that validates the student function's raw 
      output (as opposed to parsing values from it). This validation is done 
      separately from the main validator function. Like the validator, it must use
      assert, and the assert's error message is used to retrieve a message to show. 
      If omitted, no message validation will be performed.
    * *result_object_extractor* - a function that returns a result object that is 
      to be used in validation instead of the student function's return value. The
      object can be selected from the argument vector, return value(s) or parsed 
      values. If not set, this process will be skipped. Useful for testing functions
      that modify a mutable object. 
    * *argument_cloner* - a function that makes a copy of the argument vector for 
      two purposes: calling the reference without contaminating a mutable object 
      in the arguments; and being able to show the original state of the argument
      vector after the student function has been called. Usually needed for testing 
      functions that modify mutable objects. 
    * *repeat* - sets the number of times to call the student function before doing
      the evaluation. Default is 1. 
    * *new_test* - a function that is called at the start of each test case. Can be
      used to reset the state of persistent objects within the checker. Receives 
      arguments and inputs when called.
    
    Test progression is divided into two steps: one-time preparations and actual 
    test cases. One-time preparations proceed as follows.
    
    #. The handle to the original sys.stdout is saved so that it can be restored 
       later
    #. The messages dictionary is updated with messages received in the custom_msgs
       parameter
    #. Presenter functions are set for different categories
    #. If arguments and inputs are provided as functions, they are called
    #. Output is redirected to a StringOutput object
    #. Test cases are prepared by obtaining the reference result for each test 
       case - i.e. all reference results are obtained before running any tests
       before the student code has a chance to mess with things 
       
    The number of test cases is determined from the length of the test vector. Even if 
    the tested function takes no arguments, your test vector must contain an empty list
    for each test case! 
    
    Each test case is processed as follows. During the test, sys.stdout is restored
    whenever a message is shown to the student.
    
    #. new_test callback is called
    #. Stored output is cleared and output is redirected to the StringOutput object
    #. If there are inputs, a StringIO object is formed to replace sys.stdin
    #. A copy of arguments is made using argument_cloner
    #. The student function is called
    
       * If there is an error, the appropriate error message is retrieved from the 
         dictionary. Arguments and inputs (if present) are also shown in the output.
         Testing proceeds to the next case.
    
    #. If hide_output is False, the student output is shown in the evaluation 
    #. The student function output is parsed
    
       * If there is an error, OutputParseError message is shown along with 
         OutputPatternInfo. Arguments and inputs (if present) are also shown in the 
         evaluation output. Testing proceeds to the next case. 
         
    #. If result_object_extractor has been, the student function's return value
       is replaced by the callback's return value. 
    #. The validator is called
    
       * Regardless of outcome, arguments, inputs and student result are always shown.
       * If succcessful, the CorrectResult message is shown in the output.
       * If unsuccessful, the following steps are taken to provide more information.
       
         #. A message explaining the problem is shown, along with the reference result
         #. False reference functions are called and validated against the student
            result. A message corresponding to the function name is shown if
            the validation is a match. 
         #. Custom test functions are called and appropriate messages are shown if
            they raise AssertionErrors. 
         #. If test_recurrence is True, a message is printed if the student function
            returned the same result as the last test.
         #. Information functions are called and their corresponding messages are
            shown in the output, including the information function's return value.
             
    #. If test_messages is True, message_validator is called.
    
       * If successful, the CorrectMessage message is shown in the output.
       * If unsuccessful, a message explaining the problem is shown along with 
         the MessageInfo message and the student function's raw output.
    """
    
    # One time preparations
    save = sys.stdout
    msgs = copy.deepcopy(default_func_test_msgs)
    msgs.update(custom_msgs)
    
    # Set specific presenters to use generic presenter if not given
    if isinstance(presenter, dict):
        arg_presenter = presenter.get("arg", default_value_presenter)
        input_presenter = presenter.get("input", default_input_presenter)
        ref_presenter = presenter.get("ref", default_value_presenter)
        res_presenter = presenter.get("res", default_value_presenter)       
        parsed_presenter = presenter.get("parsed", default_value_presenter)
        call_presenter = presenter.get("call", default_call_presenter)
    else:        
        arg_presenter = presenter
        input_presenter = presenter
        ref_presenter = presenter
        res_presenter = presenter
        parsed_presenter = presenter
        call_presenter = presenter
    
    # call test and input producing functions 
    if inspect.isfunction(test_vector):
        test_vector = test_vector()
        
    if inspect.isfunction(inputs):
        inputs = inputs()
            
    # Show the name of the function
    #output(msgs.get_msg("FunctionName", lang).format(name=func_names[lang]), INFO)
    json_output.new_test(
        msgs.get_msg("FunctionName", lang)["content"].format(name=func_names[lang])
    )
    
    # Redirect output to string-like object
    o = StringOutput()
    sys.stdout = o
            
    # Prepare test cases. Each case is comprised of its vectors and the reference result 
    tests = []
    if ref_needs_inputs:
        test_vector = zip(test_vector, inputs)
        for v, i in test_vector:
            tests.append((v, ref_func(argument_cloner(v), i)))
    else:        
        for v in test_vector:
            tests.append((v, ref_func(*argument_cloner(v))))
    
    prev_res = None
    prev_out = None
    
    # Running tests
    for i, test in enumerate(tests):        
        json_output.new_run()

        # Test preparations
        args, ref = test
        sys.stdout = o
        o.clear()

        new_test(argument_cloner(args), inputs)

        try:
            inps = inputs[i] * repeat
            sys.stdin = io.StringIO("\n".join([str(x) for x in inps]))            
        except IndexError:
            inps = []

        stored_args = argument_cloner(args)

        # Calling the student function
        try:
            st_func = getattr(st_module, func_names[lang])
            if inspect.isfunction(st_func):
                for i in range(repeat):
                    res = st_func(*args)
            else:
                sys.stdout = save
                output(msgs.get_msg("IsNotFunction", lang), ERROR, name=func_names[lang])
                return
        except:
            sys.stdout = save
            etype, evalue, etrace = sys.exc_info()
            ename = evalue.__class__.__name__
            emsg = str(evalue)
            elineno, eline = get_exception_line(st_module, etrace)
            output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
                args=arg_presenter(stored_args),
                inputs=input_presenter(inps),
                emsg=emsg,
                ename=ename
            )
            output(msgs.get_msg("PrintExcLine", lang), DEBUG,
                lineno=elineno, line=eline
            )
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(func_names[lang], stored_args)
            )
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                    inputs=input_presenter(inps)
                )

            continue
            
        # Validating function results
        sys.stdout = save
        values_printed = False
        if not hide_output:
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)

        try:
            st_out = output_parser(o.content)
        except OutputParseError as e:
            output(msgs.get_msg("OutputParseError", lang), INCORRECT,
                args=arg_presenter(stored_args),
                inputs=input_presenter(inps),
                output=o.content,
                reason=str(e)
            )
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, 
                args=arg_presenter(stored_args), 
                call=call_presenter(func_names[lang], stored_args)
            )
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inps))                
            output(msgs.get_msg("OutputPatternInfo", lang), INFO)
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
            continue
            
        # The evaluated result must include an object that was changed during the function call
        if result_object_extractor:
            res = result_object_extractor(args, res, st_out)
            
        # Validate results
        try: 
            validator(ref, res, st_out)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            # Result was incorrect
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(func_names[lang], stored_args)
            )
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, 
                    inputs=input_presenter(inps)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
                res=res_presenter(res),
                parsed=parsed_presenter(st_out),
                output=o.content
            )
            output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
            values_printed = True
            if error_refs or custom_tests or test_recurrence:
                output(msgs.get_msg("AdditionalTests", lang), INFO)
                
            # Run false references
            for eref_func in error_refs:
                if ref_needs_inputs:
                    eref = eref_func(argument_cloner(stored_args), inps)
                else:
                    eref = eref_func(*argument_cloner(stored_args))
                try: 
                    validator(eref, res, st_out)
                    output(msgs.get_msg(eref_func.__name__, lang), INFO)
                except AssertionError as e:
                    pass
                    
            # Run custom tests
            for custom_test in custom_tests:
                try: 
                    custom_test(res, st_out, o.content, ref, stored_args, inps)
                except AssertionError as e:
                    output(msgs.get_msg(e, lang, custom_test.__name__), INFO)
            
            # Result recurrence test
            if test_recurrence and (res == prev_res or st_out and st_out == prev_out):
                output(msgs.get_msg("RepeatingResult", lang), INFO)
            
            # Run info functions
            if info_funcs:
                output(msgs.get_msg("AdditionalInfo", lang), INFO)
                for info_func in info_funcs:
                    try:
                        output(msgs.get_msg(info_func.__name__, lang), INFO,
                            func_res=info_func(res, st_out, o.content, ref, stored_args, inps)
                        )
                    except NoAdditionalInfo:
                        pass
        else:
            # Result was correct
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(func_names[lang], stored_args)
            )
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                    inputs=input_presenter(inps)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, res=res_presenter(res), parsed=parsed_presenter(st_out), output=o.content)
            values_printed = True
                
        # Validate student output    
        if message_validator:
            try: 
                message_validator(o.content, stored_args, inps)
                output(msgs.get_msg("CorrectMessage", lang), CORRECT)
            except AssertionError as e:                
                output(msgs.get_msg(e, lang, "IncorrectMessage"), INCORRECT)
                output(msgs.get_msg("MessageInfo", lang), INFO)
                output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
                if not values_printed:
                    output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                        args=arg_presenter(stored_args),
                        inputs=input_presenter(inps),
                        call=call_presenter(func_names[lang], stored_args)
                    )
                    if inputs:
                        output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                            inputs=input_presenter(inps)
                        )
        
        prev_res = res
        prev_out = st_out
            
# NOTE: custom_msgs, error_refs, custom_tests, info_funcs are read only
# therefore setting defaults to empty lists / dictionaries is safe here. 
def test_program(st_module, test_vector, ref_func,
                 lang="en",
                 custom_msgs={},
                 hide_output=True,
                 test_recurrence=True,
                 error_refs=[],
                 custom_tests=[],
                 info_funcs=[],
                 validator=parsed_result_validator,
                 presenter=default_presenters,
                 output_parser=default_parser,
                 message_validator=None,
                 new_test=default_new_test):
    """
    test_program(st_module, test_vector, ref_func[, lang="en"][, kwarg1][, ...])
    
    Tests student's main program using a set of test vectors, against a reference 
    function that emulates the desired behavior. Due to the nature of this 
    function's implementation, the student main program cannot be tested if it is
    placed inside :code:`if __name__ == "__main__":`. Overall the test procedure
    is simpler than function testing because there are no arguments to pass - 
    only inputs. 
    
    * *st_module* - a module object that's being tested
    * *test_vector* - input vectors to be given as inputs; Inputs are automatically 
      joined by newlines and made into a StringIO object that replaces standard
      input.
    * *ref_func* - reference function that is given the input vector as arguments
      and should return values that match what is expected from the student program. 
      It should **not** consume inputs (i.e. don't call :func:`input`).
    * *lang* - language for messages
    * *custom_msgs* - a TranslationDict object that includes additions/overrides 
      to the default program test messages
    * *hide_output* - a flag to show/hide student program prints in the test 
      output. By default student output is hidden. 
    * *test_recurrence* - a flag to enable/disable a convenience test that checks
      if the student code repeatedly prints the same result regardless of inputs 
      given. Default is True. 
    * *error_refs* - a list of false reference functions that will be called if the
      student program output does not match the true reference. These are useful
      for exposing common implementation errors. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *custom_tests* - a list of test functions that are called if the test is failed. 
      These tests can examine any of the test parameters and raise AssertionError if 
      problems are detected. See :ref:`Providing Debug Information <debug-information>` 
      for more about these functions. 
    * *info_funcs* - a list of information functions that are called if the test fails.
      These are similar to custom tests, but instead of making asserts, they should 
      return a value that is shown in the corresponding output message. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *validator* - the function that performs the validation of the student program
      parsed output against the reference. Validators must use assert. The assert's 
      error message is used to retrieve a message from the dictionary to show in the 
      output as the test result in case of failure.
    * *presenter* - a dictionary with any or all of the following keys: input, ref,
      res, parsed. Each key must be paired with a function that returns a string. These
      functions are used to make data structures cleaner in the output. See section
      :ref:`Presenters <presenters>` for more information.
    * *output_parser* - a function that retrieves data by parsing the student 
      program's output. Output parsers can abort the test case by raising 
      OutputParseError.
    * *message_validator* - a function that validates the student program's raw 
      output (as opposed to parsing values from it). This validation is done 
      separately from the main validator function. Like the validator, it must use
      assert, and the assert's error message is used to retrieve a message to show. 
      If omitted, message validation will not be performed. 
    * *new_test* - a function that is called at the start of each test case. Can be
      used to reset the state of persistent objects within the checker. Receives 
      arguments (as None) and inputs when called.
    
    The number of test cases is determined from the length of the test vector. Even if 
    the testing with no inputs at all, your test vector must contain an empty list
    for each test case! 
    
    Each test case is processed as follows. During the test, sys.stdout is restored
    whenever a message is shown to the student.
    
    #. new_test callback is called
    #. Stored output is cleared and output is redirected to the StringOutput object
    #. StringIO object is formed from the test vector to replace sys.stdin
    #. The student program is reloaded using :func:`importlib.reload`. 
    
       * If there is an error, the appropriate error message is retrieved from the 
         dictionary. Inputs are also shown in the output. Testing proceeds to the next 
         case.
    
    #. If hide_output is False, the student output is shown in the evaluation 
    #. The student function output is parsed
    
       * If there is an error, OutputParseError message is shown along with 
         OutputPatternInfo. Inputs are also shown in the evaluation output. Testing 
         proceeds to the next case. 
         
    #. The validator is called 
    
       * Regardless of outcome, inputs and student result are always shown.
       * If succcessful, the CorrectResult message is shown in the output.
       * If unsuccessful, the following steps are taken to provide more information
       
         #. A message explaining the problem is shown, along with the reference.
         #. False reference functions are called and validated against the student 
            result. A message corresponding to the function name is shown if
            the validation is a match.
         #. Custom test functions are called and appropriate messages are shown if
            they raise AssertionErrors.
         #. If test_recurrence is True, a message is printed if the student program
            produced the same result as the last test.
         #. Information functions are called and their corresponding messages are
            shown in the output, including the information function's return value.
             
    #. If test_messages is True, message_validator is called.
    
       * If successful, the CorrectMessage message is shown in the output.
       * If unsuccessful, a message explaining the problem is shown along with 
         the MessageInfo message and the student program's raw output.
    """


    # One time preparations
    save = sys.stdout
    msgs = copy.deepcopy(default_program_test_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        input_presenter = presenter.get("input", default_input_presenter)
        ref_presenter = presenter.get("ref", default_value_presenter)
        parsed_presenter = presenter.get("parsed", default_value_presenter)
    else:        
        input_presenter = presenter
        ref_presenter = presenter
        parsed_presenter = presenter


    if inspect.isfunction(test_vector):
        test_vector = test_vector()
    
    #output(msgs.get_msg("ProgramName", lang).format(name=st_module.__name__), INFO)
    json_output.new_test(
        msgs.get_msg("ProgramName", lang)["content"].format(name=st_module.__name__)
    )

    o = StringOutput()
    sys.stdout = o
    
    tests = []
    for v in test_vector:
        tests.append((v, ref_func(*v)))
    
    prev_out = None
    
    # Running the tests
    for inputs, ref in tests:
        json_output.new_run()
        new_test(None, inputs)
        reset_locals(st_module)
        
        # Test preparations
        sys.stdout = o
        o.clear()
            
        sys.stdin = io.StringIO("\n".join([str(x) for x in inputs]))
        
        # Running the student module
        try:
            importlib.reload(st_module)
        except:
            sys.stdout = save
            etype, evalue, etrace = sys.exc_info()
            ename = evalue.__class__.__name__
            emsg = str(evalue)
            elineno, eline = get_exception_line(st_module, etrace)
            output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
                inputs=input_presenter(inputs),
                emsg=emsg,
                ename=ename
            )
            output(msgs.get_msg("PrintExcLine", lang), DEBUG, lineno=elineno, line=eline)
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))
            return 
            
        # Validating program results
        values_printed = False
        sys.stdout = save
        if not hide_output:
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
                
        # Parse output
        try:
            st_out = output_parser(o.content)
        except OutputParseError as e:
            output(msgs.get_msg("OutputParseError", lang), INCORRECT,
                inputs=input_presenter(inputs),
                output=o.content,
                reason=str(e)
            )
            output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                inputs=input_presenter(inputs)
            )
            output(msgs.get_msg("OutputPatternInfo", lang), INFO)
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
            continue

        # Validation
        try: 
            validator(ref, None, st_out)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            # Result was incorrect
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG,
                parsed=parsed_presenter(st_out), output=o.content
            )
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)  
            output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
            values_printed = True
            if error_refs or custom_tests or test_recurrence:
                output(msgs.get_msg("AdditionalTests", lang), INFO)
            
            # Run false references
            for eref_func in error_refs:
                eref = eref_func(*inputs)
                try: 
                    validator(eref, None, st_out)
                    output(msgs.get_msg(eref_func.__name__, lang), INFO)
                except AssertionError as e:
                    pass
                    
            # Run custom tests
            for test in custom_tests:
                try: 
                    test(None, st_out, o.content, ref, None, inputs)
                except AssertionError as e:
                    output(msgs.get_msg(e, lang, test.__name__), INFO)
                    
            # Test for result recurrence
            if test_recurrence and st_out == prev_out:
                output(msgs.get_msg("RepeatingResult", lang), INFO)

            # Run info functions
            if info_funcs:
                output(msgs.get_msg("AdditionalInfo", lang), INFO)
                for info_func in info_funcs:
                    try:
                        output(msgs.get_msg(info_func.__name__, lang), INFO,
                            func_res=info_func(None, st_out, o.content, ref, None, inputs)
                        )
                    except NoAdditionalInfo:
                        pass
        else:
            # Result was correct
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG,
                parsed=parsed_presenter(st_out),
                output=o.content
            )
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)  
            values_printed = True

        # Validate student output
        if message_validator:
            try: 
                message_validator(o.content, None, inputs)
                output(msgs.get_msg("CorrectMessage", lang), CORRECT)
            except AssertionError as e:
                output(msgs.get_msg(e, lang, "IncorrectMessage"), INCORRECT)
                output(msgs.get_msg("MessageInfo", lang), INFO)
                if not values_printed:
                    output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)  
                    output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                        inputs=input_presenter(inputs)
                    )
                
        prev_out = None


# NOTE: custom_msgs, inputs, error_refs, custom_tests, info_funcs are read only
# therefore setting defaults to empty lists / dictionaries is safe here. 
def test_code_snippet(st_code, constructor, ref_func, 
                      lang="en",
                      custom_msgs={},
                      inputs=[],
                      hide_output=True,
                      error_refs=[],
                      custom_tests=[],
                      info_funcs=[],
                      validator=vars_validator,
                      presenter=default_presenters,
                      output_parser=default_parser,
                      message_validator=None):
    """
    test_code_snippet(st_code, constructor, ref_func[, lang="en"][, kwarg1][, ...])
    
    Tests a code snippet. The snippet can be put into a larger context by using
    a *constructor* function. The snippet along with its context is written into
    a temporary module and run. After running the namespace of the module is
    evaluated against a reference object provided by the reference function.
    
    * *st_code* - a string that contains the code snippet
    * *constructor* - a function that creates a full program around the snippet.
      This can include setting initial values for variables etc.
    * *ref_func* - reference function that is given the input vector as arguments
      and should return an object that can be compared with the student
      submission's namespace. It should **not** consume inputs (i.e. don't call
      :func:`input`).
    * *lang* - language for messages
    * *custom_msgs* - a TranslationDict object that includes additions/overrides 
      to the default code snippet test messages
    * *hide_output* - a flag to show/hide student program prints in the test 
      output. By default student output is hidden. 
    * *error_refs* - a list of false reference functions that will be called if the
      student program output does not match the true reference. These are useful
      for exposing common implementation errors. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *custom_tests* - a list of test functions that are called if the test is failed. 
      These tests can examine any of the test parameters and raise AssertionError if 
      problems are detected. See :ref:`Providing Debug Information <debug-information>` 
      for more about these functions. 
    * *info_funcs* - a list of information functions that are called if the test fails.
      These are similar to custom tests, but instead of making asserts, they should 
      return a value that is shown in the corresponding output message. See 
      :ref:`Providing Debug Information <debug-information>` for more about these 
      functions. 
    * *validator* - the function that performs the validation of the student program
      parsed output against the reference. Validators must use assert. The assert's 
      error message is used to retrieve a message from the dictionary to show in the 
      output as the test result in case of failure.
    * *presenter* - a dictionary with any or all of the following keys: input, ref,
      vars, parsed. Each key must be paired with a function that returns a string. These
      functions are used to make data structures cleaner in the output. See section
      :ref:`Presenters <presenters>` for more information.
    * *output_parser* - a function that retrieves data by parsing the student 
      program's output. Output parsers can abort the test case by raising 
      OutputParseError.
    * *message_validator* - a function that validates the student program's raw 
      output (as opposed to parsing values from it). This validation is done 
      separately from the main validator function. Like the validator, it must use
      assert, and the assert's error message is used to retrieve a message to show. 
      If omitted, message validation will not be performed. 
    
    Currently code snippet tests only run once. They proceed as follows:
    
    #. Real stdout is saved, messages are updated from custom messages given by
       the checker and presenters are set. Inputs are written into a StringIO 
       and stdin is pointed there.
    #. The reference result is obtained from the reference function.
    #. Student submission is constructed into a temporary module using the constructor.
       The module is written into a file.
    #. The code is executed by importing the temporary module. 

       * If there is an error, the appropriate error message is retrieved from the 
         dictionary. Inputs are also shown in the output. Testing is aborted.
    
    #. Output is printed unless *hide_output* is True.
    #. The output is parsed for values.

       * If there is an error, OutputParseError message is shown along with 
         OutputPatternInfo. Inputs are also shown in the evaluation output. Testing 
         is aborted.
         
    #. The validator is run, comparing the namespaces of the temporary modules against
       a reference object, or parsed values against the reference (or both). 
       
       * Regardless of outcome, inputs and student result are always shown.
       * If succcessful, the CorrectResult message is shown in the output.
       * If unsuccessful, the following steps are taken to provide more information
       
         #. A message explaining the problem is shown, along with the reference.
         #. False reference functions are called and validated against the student 
            result. A message corresponding to the function name is shown if
            the validation is a match.
         #. Custom test functions are called and appropriate messages are shown if
            they raise AssertionErrors.
         #. If test_recurrence is True, a message is printed if the student program
            produced the same result as the last test.
         #. Information functions are called and their corresponding messages are
            shown in the output, including the information function's return value.
    """
    
    
    # One time preparations
    correct = True
    
    save = sys.stdout
    msgs = copy.deepcopy(default_code_snippet_test_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        input_presenter = presenter.get("input", default_input_presenter)
        ref_presenter = presenter.get("ref_vars", default_vars_presenter)
        parsed_presenter = presenter.get("parsed", default_value_presenter)
        vars_presenter = presenter.get("vars", default_vars_presenter)        
    else:        
        input_presenter = presenter
        ref_presenter = presenter
        parsed_presenter = presenter
        vars_presenter = presenter
        
    json_output.new_test(msgs.get_msg("SnippetTest", lang)["content"])
    
    o = StringOutput()
    sys.stdout = o
    
    json_output.new_run()
    
    sys.stdout = o
    o.clear()
        
    sys.stdin = io.StringIO("\n".join([str(x) for x in inputs]))
    
    ref = ref_func(inputs)
    
    # Construct the module and write it to a file
    full_code = constructor(st_code)
    with open("temp_module.py", "w") as target:
        target.write(full_code)
    
    # Load the module and obtain output
    try:
        temp_module = importlib.import_module("temp_module")
    except:
        sys.stdout = save
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
            ename=ename,
            emsg=emsg,
            inputs=input_presenter(inputs)
        )
        if inputs:
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=presenter(inputs))
        return False

    # Resume output to normal stdout and show output if not hidden
    values_printed = False
    sys.stdout = save
    if not hide_output:
        output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)

    # Parse the output into a result
    try:
        st_out = output_parser(o.content)
    except OutputParseError as e:
        output(msgs.get_msg("OutputParseError", lang), INCORRECT,
            inputs=input_presenter(inputs),
            output=o.content,
            reason=str(e)
        )
        output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))
        output(msgs.get_msg("OutputPatternInfo", lang), INFO)
        output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
        return False

    # Validate the result
    try:
        validator(ref, temp_module, st_out)
        output(msgs.get_msg("CorrectResult", lang), CORRECT)
    except AssertionError as e:
        # Result was incorrect
        correct = False
        output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
        if inputs:
            output(msgs.get_msg("PrintInputVector", lang), DEBUG,
                inputs=presenter(inputs)
            )
        output(msgs.get_msg("PrintStudentResult", lang), DEBUG,
            res=vars_presenter(temp_module),
            parsed=st_out,
            output=o.content
        )
        if o.content:
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)
        output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
        value_printed = True
        if error_refs or custom_tests:
            output(msgs.get_msg("AdditionalTests", lang), INFO)

        # Run validation against false references
        for eref_func in error_refs:
            eref = eref_func(inputs)
            try: 
                validator(ref, temp_module, st_out)
                output(msgs.get_msg(eref_func.__name__, lang), INFO)
            except AssertionError as e:
                pass

        # Run custom tests
        for test in custom_tests:
            try: 
                test(temp_module, st_out, o.content, ref, None, inputs)
            except AssertionError as e:
                output(msgs.get_msg(e, lang, test.__name__), INFO)

        # Run info functions
        if info_funcs:
            output(msgs.get_msg("AdditionalInfo", lang), INFO)
            for info_func in info_funcs:
                try:
                    output(msgs.get_msg(info_func.__name__, lang), INFO, 
                        func_res=info_func(temp_module, st_out, o.content, ref, None, inputs)
                    )
                except NoAdditionalInfo:
                    pass
    else:
        # Result was correct
        if inputs:
            output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))
        output(msgs.get_msg("PrintStudentResult", lang), DEBUG,
            res=vars_presenter(temp_module),
            parsed=st_out,
            output=o.content
        )
        values_printed = True

    # Validate output messages
    if message_validator:
        try: 
            message_validator(o.content, None, inputs)
            output(msgs.get_msg("CorrectMessage", lang), CORRECT)
        except AssertionError as e:
            correct = False
            output(msgs.get_msg(e, lang, "IncorrectMessage"), INCORRECT)
            output(msgs.get_msg("MessageInfo", lang), INFO)
            if not values_printed:
                output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=o.content)  
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inputs))

    return correct

# NOTE: custom_msgs is read only
# therefore setting defaults to empty dictionary is safe here. 
def static_test(st_module, func_names, lang, validators, info_only=False, custom_msgs={}):
    """
    static_test(st_module, func_names, lang, validators[, info_only=False[, custom_msgs={}]])
    
    This function performs static tests - i.e. tests that examine the source code
    of the student's program instead of executing it. If *func_names* is a 
    dictionary of languages and corresponding function names, the soure code of 
    that function is subjected to testing. If it is set to None, the module's 
    source code is examined instead. 
    
    The test runs a set of *validators* which should be functions that receive 
    the source code, docstring and comments as seperate arguments. It should use
    asserts. Like in other tests, assert messages are fetched from the message
    dictionary (which can be updated by providing *custom_msgs*). 
    
    If the optional *info_only* flag is set to True, the output in case of issues
    found in the source code is classified as INFO instead of ERROR. This allows 
    you to give the student feedback about dubious solutions without necessarily 
    causing their code to fail the evaluation. 
    """
    
    msgs = copy.deepcopy(default_static_test_msgs)
    msgs.update(custom_msgs)
    
    #output(msgs.get_msg("StaticTest", lang).format(fname=func_names.get(lang, "")), INFO)
    json_output.new_test(
        msgs.get_msg("StaticTest", lang)["content"].format(fname=func_names.get(lang, ""))
    )
    json_output.new_run()
    
    try:
        if func_names:
            st_func = getattr(st_module, func_names[lang])
            source, doc, comments = inspect.getsource(st_func), inspect.getdoc(st_func), inspect.getcomments(st_func)
        else:
            source, doc, comments = inspect.getsource(st_module), inspect.getdoc(st_module), inspect.getcomments(st_module)
    except:
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
            fname=func_names.get(lang, ""),
            emsg=emsg,
            ename=ename
        )
        return 
        
    failed = 0
    for validator in validators:
        try: 
            validator(source, doc, comments)
        except AssertionError as e:
            if info_only:
                output(msgs.get_msg(e, lang, validator.__name__), INFO)
            else:
                output(msgs.get_msg(e, lang, validator.__name__), ERROR)
                failed += 1
    
    if not failed:
        output(msgs.get_msg("CorrectResult", lang), CORRECT)


# NOTE: extra_options, custom_msgs are read only
# therefore setting defaults to empty lists / dictionaries is safe here. 
def pylint_test(st_module,
                lang="en",
                extra_options=[],
                validator=default_pylint_validator,
                info_only=True,
                custom_msgs={}):
    
    """
    pylint_test(st_module[, lang="en"][, kwarg1][, ...])
    
    Performs a PyLint check on the submitted code module. Mostly just runs PyLint
    inside Python and parses its feedback into messages. Unfortunately PyLint does
    not seem to support gettext so its feedback is always in English. This function
    can be given *extra_options* to be passed to PyLint. Beyond that it uses
    PyLint's configuration discovery. The test can be set to *info_only* in which
    case it never rejects the submission unless there's an error reported by the
    linter. A *validator* can also be provided.
    
    See https://pylint.readthedocs.io/en/latest/user_guide/run.html for information
    regarding configuration and options.
    """
    
    msgs = copy.deepcopy(default_lint_test_msgs)
    msgs.update(custom_msgs)
    
    json_output.new_test(msgs.get_msg("LintTest", lang)["content"])
    json_output.new_run()
    
    options_list = extra_options + ["--output-format=json", st_module.__file__]
    
    save_o = sys.stdout
    save_e = sys.stderr
    
    o = StringOutput()
    e = StringOutput()
    
    sys.stdout = o
    sys.stderr = e
    
    try:
        result = lint.Run(options_list, do_exit=False)
    except:
        etype, evalue, etrace = sys.exc_info()
        sys.stdout = save_o
        sys.stderr = save_e
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, emsg=emsg, ename=ename)
        return 

    sys.stdout = save_o
    sys.stderr = save_e
            
    try:
        validator(result.linter.stats)
    except AssertionError as e:
        if info_only:
            output(msgs.get_msg(e, lang, "LintFailMessage"), INFO, **result.linter.stats)
        else:
            output(msgs.get_msg(e, lang, "LintFailMessage"), INCORRECT, **result.linter.stats)
    else:
        output(msgs.get_msg("LintSuccess", lang), CORRECT, **result.linter.stats)
        
    output(msgs.get_msg("LintMessagesBegin", lang), INFO)
    
    for msg in result.linter.reporter.messages:
        if msg["type"] == "convention":
            output(msgs.get_msg("LintConvention", lang), LINT_C, **msg)
        elif msg["type"] == "refactor":
            output(msgs.get_msg("LintRefactor", lang), LINT_R, **msg)
        elif msg["type"] == "warning":
            output(msgs.get_msg("LintWarning", lang), LINT_W, **msg)
        elif msg["type"] == "error":
            output(msgs.get_msg("LintError", lang), LINT_E, **msg)
        elif msg["type"] == "fatal":
            output(msgs.get_msg("LintFatal", lang), ERROR, **msg)


## Cleanup stuff ##
    
def end():
    """
    This function gets called automatically when this module exits. It prints
    the JSON document into stdout.
    
    You can pipe the output to the cli_print script to get a more readable 
    representation when testing checkers in a command line interface.
    """
        
    print(json.dumps(json_output))
    
atexit.register(end)
        
