"""


"""

import cffi
import copy
import os
import re
import sys
import random
from test_core import *

alnum = "abcdefghijklmnopqrstuvwxyz0123456789"

dlm = default_load_msgs = TranslationDict()
dlm.set_msg("GenericErrorMsg", "fi", dict(content="Koodin lataaminen kirjastona epäonnistui.\nLisätietoja: {emsg}"))
dlm.set_msg("GenericErrorMsg", "en", dict(content="Failed to load the code as a library.\nInformation: {emsg}"))
dlm.set_msg("OSError", "fi", dict(content="{emsg}"))
dlm.set_msg("OSError", "en", dict(content="{esmg}"))
dlm.set_msg("NoStdIO", "fi", dict(content="Koodista puuttui stdio-kirjaston include, jota tarvitaan tulostukseen ja syötteiden lukemiseen."))
dlm.set_msg("NoStdIO", "en", dict(content="Your code is missing an include for stdio which is needed for printing and reading input."))
dlm.set_msg("LoadingLibrary", "fi", dict(content="Ladataan kooditiedosto {name} kirjastona testattavaksi..."))
dlm.set_msg("LoadingLibrary", "en", dict(content="Loading source code file {name} as a library for testing..."))
dlm.set_msg("CompileError", "fi", dict(
    content="Kooditiedostoa ei voitu kääntää.",
    hints=["Tarkista koneellasi, että koodi kääntyy.", "Tarkista, että koodissa on kaikki tehtävänannon tyyppimäärittelyt."]
))
dlm.set_msg("CompileError", "en", dict(
    content="Unable to compile the source file.",
    hints=["Make sure the code compiles on your computer.", "Make sure you have included all type definitions from the specification."]
))
dlm.set_msg("EncodingError", "fi", dict(
    content="Kooditiedostoa ei voitu lukea UTF-8 koodauksella.",
    hints=["Varmista, että tiedoston koodaus on UTF-8 tai poista sieltä kaikki ääkköset ja muut erikoismerkit - myös kommenteista."]
))
dlm.set_msg("EncodingError", "en", dict(
    content="Unable to read the code file as UTF-8.",
    hints=["Make sure your code file's encoding is UTF-8, or remove any non-ascii characters (even from comments)."]
))
dlm.set_msg("InvalidPrototype", "fi", dict(
    content="Yksi tai useampi funktion prototyyppi sisälsi virheitä. Tarkistinjärjestelmä asettaa prototyypeille joitain rajoituksia."
))
dlm.set_msg("InvalidPrototype", "en", dict(
    content="One ore more prototypes contained errors. The checking system places certain additional limits for prototypes."
))

    

ftme = function_test_msg_extension = TranslationDict()
ftme.set_msg("OutputEncodingError", "fi", dict(content="Koodin tulostus sisälsä lukukelvottomia merkkejä."))
ftme.set_msg("OutputEncodingError", "en", dict(content="Your code's output included garbage characters."))

default_func_test_msgs.update(ftme)



proto_pat = re.compile("(?:[A-Za-z0-9_]+\s+)+[A-Za-z0-9_]+\s*\((?:[A-Za-z0-9_\* ]+,?)*\)\s*;")
cdata_pat = re.compile("<cdata '(?P<type>[A-Za-z0-9_ \*]+)' owning (?P<bytes>[0-9]+) bytes>")

ffi = cffi.FFI()

def gen_random_binary(bits):
    """
    gen_random_binary(bits) -> str
    
    This convenience function creates a randomized string with the given number
    of *bits*. Useful for testing functions that perform bitwise operations. 
    """
    
    i = random.randint(0, 2 ** bits - 1)
    return bin(i)[2:].rjust(bits, "0")

def find_prototypes(content):
    """
    find_prototypes(content) -> list
    
    This function locates function prototypes from a .c file. These are needed 
    for defining the functions within CFFI. It's a work in progress and at its 
    present stage can sometimes fail to find prototypes even if they are 
    there. The function is not used for .h files.
    """
    
    
    protos = []
    comment = False
    for line in content:
        #if line.strip().endswith("{") and not line.strip().startswith("struct"):
        #    break
        line = line.strip()
        
        if "/*" in line:
            if "*/" not in line:
                comment = True
        if comment and "*/" in line:
            comment = False
        
        if not comment:
            line = line.split("//")[0].split("/*")[0].strip()
            if line.endswith(";") and not line.startswith("return"):
                if proto_pat.match(line):
                    protos.append(line)
    return protos


def aggressive_rounding_validator(ref, res, out):
    """
    This convenience validator performs more aggressive rounding validation for
    floats than the rounding validator in the core module. It rounds off all 
    decimals. This can sometimes be useful if dealing with results with a lot 
    of decimals. 
    """    
    
    assert round(ref) == round(res)

def input_to_file(content):
    """
    input_to_file(content) -> str
    
    This function is used internally to put inputs into a file - the method
    used by the core module (using StringIO) does not change where C code looks
    for its stdin. This function prepares a file that where we can redirect 
    stdin for the C code.
    """
    
    fn = "".join([random.choice(alnum) for i in range(16)])
    with open(fn, "w") as f:
        f.write(content + "\n")
    return fn

# https://stackoverflow.com/questions/20000332/repeated-redirection-of-low-level-stdin-in-python
def freopen(f, mode, stream):
    """
    This function is used internally to redirect stdin and stdout to files. The
    method used by the core module is not sufficient for testing C code which 
    is why we need to manipulate file descriptors through the os module instead. 
    """
    
    oldf = open(f, mode)
    oldfd = oldf.fileno()
    newfd = stream.fileno()
    os.close(newfd)
    os.dup2(oldfd, newfd)

def default_c_presenter(value):
    """
    default_c_presenter(value) -> str
    
    .. deprecated:: 0.5
        
    This is the default presenter used by C function tests. Currently it is 
    just a dummy as the presenter system is undergoing modifications. 
    """
    
    
    if isinstance(value, (list, tuple)):
        parts = []
        for val in value:
            if isinstance(val, ffi.CData):
                parts.append(str(val))
                #ctype = cdata_pat.search(str(val)).groupdict()["type"]
                #if "*" in ctype:
                #    parts.append(ctype + "->" + str(val[0]))
                #elif "[" in ctype:
                #    pass #array printing
                    
            else:
                parts.append(str(val))
                
        return " ".join(parts)    
    
    else:
        if isinstance(value, ffi.CData):
            return value
            #ctype = cdata_pat.search(str(value)).groupdict()["type"]
            #if "*" in ctype:
            #    return ctype + "->" + str(value[0])
            #elif "[" in ctype:
            #    pass
        else:
            return value        
        
def default_c_call_presenter(func_name, args):
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
        call += ");"
    
    return "{{{highlight=c\n" + call + "\n}}}"        
        
def default_c_value_presenter(value):
    return repr(value)            

def load_with_verify(st_c_filename, lang="en", custom_msgs={}, typedefs={}, req_stdio=False):
    lib_name, ext = os.path.splitext(st_c_filename)
    msgs = default_load_msgs.copy()
    msgs.update(custom_msgs)
    
    json_output.new_test(msgs.get_msg("LoadingLibrary", lang)["content"].format(name=st_c_filename))
    json_output.new_run()    
    
    fd_o = sys.stderr.fileno()
    orig_stderr = os.fdopen(os.dup(fd_o), "w")
    
    save = sys.stderr
    
    if typedefs:
        for td in typedefs[lang]:
            ffi.cdef(td)
        
    if os.path.exists(lib_name + ".h"):
        headers = lib_name + ".h"
    else:
        headers = lib_name + ".c"
                
    try:
        with open(headers, encoding="utf-8-sig") as source:
            contents = source.readlines()
            protos = find_prototypes(contents)
        
            ffi.cdef("\n".join(protos))
    except UnicodeDecodeError:
        output(msgs.get_msg("EncodingError", lang), ERROR)
        return None
        
        
    if req_stdio:
        ffi.cdef("FILE* stdout;")
        ffi.cdef("void setbuf(FILE *stream, char *buf);")

    freopen("err", "w", sys.stderr)

    with open(st_c_filename) as source:
        try:
            st_lib = ffi.verify(source.read())
        except:
            os.dup2(orig_stderr.fileno(), sys.stderr.fileno())
            output(msgs.get_msg("CompileError", lang), ERROR)
            with open("err", "r") as f:
                print(f.read())
            return None
        
    os.dup2(orig_stderr.fileno(), sys.stderr.fileno())

    if req_stdio:
        try:
            st_lib.setbuf(st_lib.stdout, ffi.NULL)
        except AttributeError:
            output(msgs.get_msg("NoStdIO", lang), ERROR)
            return None
    
    return st_lib
    
    
    
    

def load_library(st_c_filename, so_name, lang="en", custom_msgs={}, typedefs={}, req_stdio=False):
    """
    load_library(st_c_filename, so_name[, lang="en"][, custom_msgs={}][, typedefs={}][, req_stdio=False]) -> CFFI dynamic library object
    
    This function loads the student code as a library so that we can later call
    its functions. The loading has two parts: initializing the CFFI dynamic 
    library object, and defining the function headers. Both of these are 
    hanled by `Link CFFI <http://cffi.readthedocs.io/en/latest/index.html>`_. 
    In order to load the library, *so_name* must match the name given to the 
    .so (or dll in Windows) when compiling. The argument is given as a 
    dictionary with language codes as keys and corresponding so names as 
    values. 
    
    In the current implemenation struct definitions and similar are not parsed 
    from .c files (but they are parsed from .h files). Instead, if students are 
    epxected to use given structs, their definitios should be included in the 
    *typedefs* argument. Note that this is only needed for types that need to 
    be exposed to the checker - and usually in these situations you should 
    already know what they are going to be. E.g. if you need to give pointers 
    to structs in the test vector, then the definition of that struct needs to
    be in the *typedefs* dictionary. This dictionary has language codes as its
    keys and definition strings as values. All types should be in one string. 
    
    If the student code is expected to print something that needs to be 
    evaluated, then *req_stdio* must be set to True. There is a degree of 
    mysticism involved in redirecting C stdio to files and setting the flag to
    True performs that particular sorcery. However, it fails if the student 
    code does not include stdio. A message is shown in the output in this case.
    """
    
    lib_name, ext = os.path.splitext(st_c_filename)
    so_name = so_name.get(lang, so_name["en"])
    msgs = copy.deepcopy(default_load_msgs)
    msgs.update(custom_msgs)
    
    json_output.new_test(msgs.get_msg("LoadingLibrary", lang)["content"].format(name=st_c_filename))
    json_output.new_run()    

    if "/" not in lib_name:
        lib_name = "./" + lib_name
    
    try:
        st_lib = ffi.dlopen("./" + so_name + ".so")
    except:
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, ename=ename, emsg=emsg)
        return None
    
    if typedefs:
        for td in typedefs[lang]:
            ffi.cdef(td)
        
    if os.path.exists(lib_name + ".h"):
        headers = lib_name + ".h"
    else:
        headers = lib_name + ".c"

    try:
        with open(headers, encoding="utf-8-sig") as source:
            contents = source.readlines()
            protos = find_prototypes(contents)
            
            ffi.cdef("\n".join(protos)) 
    except UnicodeDecodeError:
        output(msgs.get_msg("EncodingError", lang), ERROR)
        return None
    except cffi.api.CDefError:
        output(msgs.get_msg("InvalidPrototype", lang), ERROR)
        return None
        
    
    # magic workaround; without this stdout redirects in the test_c_function function don't work.
    # the workaround sets the C stdout buffer to NULL which forces it to output everything 
    # without buffering. 
    
    if req_stdio:
        try:
            ffi.cdef("FILE* stdout;")
            ffi.cdef("void setbuf(FILE *stream, char *buf);")
            st_lib.setbuf(st_lib.stdout, ffi.NULL)
        except AttributeError:
            output(msgs.get_msg("NoStdIO", lang), ERROR)
            return None
    
    return st_lib
    
default_c_presenters = {
    "arg": default_c_value_presenter,
    "input": default_input_presenter, 
    "ref": default_c_value_presenter,
    "res": default_c_value_presenter,
    "parsed": default_value_presenter   ,
    "call": default_c_call_presenter
}
    
    
def test_c_function(st_module, func_names, test_vector, ref_func, lang="en", custom_msgs={}, inputs=[], hide_output=True, test_recurrence=True, ref_needs_inputs=False, error_refs=[], custom_tests=[], info_funcs=[], validator=result_validator, presenter=default_c_presenters, output_parser=default_parser, message_validator=None, result_object_extractor=None, argument_cloner=default_argument_cloner, repeat=1, new_test=default_new_test): 
    """
    test_c_function(st_module, func_names, test_vector, ref_func[, lang="en"][, kwarg1][, ...])
    
    Tests a student's C function with a set of test vectors, against a reference 
    function. The behavior of this function can be customized heavily by using 
    callbacks and other optional keyword arguments. All arguments are listed and
    explained below. From the checker development perspective this function is 
    almost identical with the core module's test_function. Important differences 
    are highlighted. 
    
    * *st_module* - a module object that contains the function that's being tested
    * *func_names* - a dictionary that has two character language codes as keys and
      corresponding function name in that language as values
    * *test_vector* - a list of argument vectors or a function that generates the 
      the list. This vector must be sequences within a list, where each sequence 
      is one test case. Each case vector is unpacked when reference and student 
      functions are called. **Important**: all string must be bytestrings.
    * *ref_func* - reference function that gets called with the same arguments as
      the student function to obtain the reference result for each test case.
    * *lang* - language for messages and for finding the student function
    * *custom_msgs* - a TranslationDict object that includes additions/overrides 
      to the default function test messages
    * *inputs* - input vectors to be given to the function; must have as many vectors 
      as test_vector. Inputs are automatically put into separate lines in a file
      that is redirected to stdin on the operating system level.
    * *ref_needs_inputs* - if set to True, the reference function is given two 
      lists instead of unpacking the argument vector for each case. In this case 
      the reference function is always called with exactly two parameters: list of 
      arguments and list of inputs. Default is False. This behavior is necessary if
      your reference function needs to change its result based on inputs. 
    * *validator* - the function that performs the validation of the student function
      return value and/or parsed output against the reference. Validators must use 
      assert. The assert's error message is used to retrieve a message from the 
      dictionary to show in the output as the test result in case of failure.
    * *message_validator* - a function that validates the student function's raw 
      output (as opposed to parsing values from it). This validation is done 
      separately from the main validator function. Like the validator, it must use
      assert, and the assert's error message is used to retrieve a message to show. 
    * *output_parser* - a function that retrieves data by parsing the student 
      function's output. Values obtained by the parser are offered separately from 
      the function's return values to the validator. Output parsers can abort the 
      test case by raising OutputParseError.
    * *result_object_extractor* - a function that returns a result object that is 
      to be used in validation instead of the student function's return value. The
      object can be selected from the argument vector, return value(s) or parsed 
      values. If not set, this process will be skipped. Useful for testing functions
      that modify a mutable object. Works for anything that is passed with pointers.
    * *presenter* - a function or a dictionary with any or all of the following keys:
      arg, input, ref, res, parsed. Each key must be paired with a function that 
      returns a string. These functions are used to make data structures cleaner in 
      the output. See section :ref:`C Presenters <c-presenters>` for more 
      information.
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
    * *hide_output* - a flag to show/hide student function prints in the test 
      output. By default student output is hidden. 
    * *test_recurrence* - a flag to enable/disable a convenience test that checks
      if the student code repeatedly returns the same result regardless of 
      arguments/inputs given to the function. Default is True. Should be disabled
      for functions that don't return anything to avoid confusing messages.
    * *argument_cloner* - a function that makes a copy of the argument vector for 
      two purposes: calling the reference without contaminating a mutable object 
      in the arguments; and being able to show the original state of the argument
      vector after the student function has been called. Usually needed for testing 
      functions that modify mutable objects. 
    * *repeat* - sets the number of times to call the student function before doing
      the evaluation. Default is 1. 
    * *new_test* - a function that is called at the start of each test case. Can be
      used to reset the state of persistent objects within the checker. 
    
    Test progression is divided into two steps: one-time preparations and actual 
    test cases. One-time preparations proceed as follows.
    
    #. The file descriptor of the original sys.stdout is saved so that it can be 
       restored later
    #. The messages dictionary is updated with messages received in the custom_msgs
       parameter
    #. Presenter functions are set for different categories
    #. If arguments and inputs are provided as functions, they are called
    #. Output is redirected to a file
    #. Test cases are prepared by obtaining the reference result for each test 
       case - i.e. all reference results are obtained before running any tests
       before the student code has a chance to mess with things 
       
    The number of test cases is determined from the length of the test vector. Even if 
    the tested function takes no arguments, your test vector must contain an empty list
    for each test case! 
    
    Each test case is processed as follows. During the test, sys.stdout is restored
    whenever a message is shown to the student.
    
    #. new_test callback is called
    #. Stored output file is cleared and output is redirected to it
    #. If there are inputs, an input file is formed and stdin is redirected to it
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
    
       * If succcessful, the CorrectResult message is shown in the output.
       * If unsuccessful, the following steps are taken to provide more information
       
         #. A message explaining the problem is shown, along with arguments, inputs 
            (if present), the reference result and the student result.
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
         the MessageInfo message and the student function's raw output. If arguments
         and inputs have not been shown yet, they are also shown. 
         
    #. The temporary input file is deleted
    """


    # One time preparations
    fd_o = sys.stdout.fileno()
    fd_i = sys.stdin.fileno()
    orig_stdout = os.fdopen(os.dup(fd_o), "w")
    orig_stdin = os.fdopen(os.dup(fd_i), "r")

    save = sys.stdout
    msgs = default_func_test_msgs.copy()
    msgs.update(custom_msgs)

    # Set specific presenters to use generic presenter if not given
    if isinstance(presenter, dict):
        arg_presenter = presenter.get("arg", default_c_value_presenter)
        input_presenter = presenter.get("input", default_input_presenter)
        ref_presenter = presenter.get("ref", default_c_value_presenter)
        res_presenter = presenter.get("res", default_c_value_presenter)       
        parsed_presenter = presenter.get("parsed", default_value_presenter)
        call_presenter = presenter.get("call", default_c_call_presenter)
    else:        
        arg_presenter = presenter
        input_presenter = presenter
        ref_presenter = presenter
        res_presenter = presenter
        parsed_presenter = presenter
        call_presenter = presenter
    
    if inspect.isfunction(test_vector):
        test_vector = test_vector()
        
    if inspect.isfunction(inputs):
        inputs = inputs()
            
            
    json_output.new_test(msgs.get_msg("FunctionName", lang)["content"].format(name=func_names[lang]))
    
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
        freopen("output", "w", sys.stdout)
        
        # Test preparations
        args, ref = test
        new_test(args, inputs)
                    
        try:
            inps = inputs[i] * repeat
            fn = input_to_file("\n".join([str(x) for x in inps]))
            freopen(fn, "r", sys.stdin)
        except IndexError:
            inps = []
        
        stored_args = argument_cloner(args)
        
        # Calling the student function
        try:
            st_func = getattr(st_module, func_names[lang])
            for i in range(repeat):
                res = st_func(*args)
        except:
            os.dup2(orig_stdout.fileno(), sys.stdout.fileno())
            etype, evalue, etrace = sys.exc_info()
            ename = evalue.__class__.__name__
            emsg = str(evalue)
            output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, args=arg_presenter(stored_args), inputs=input_presenter(inps), emsg=emsg, ename=ename)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, args=arg_presenter(stored_args), call=call_presenter(func_names[lang], stored_args), inputs=input_presenter(inps))
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inps))
            return
            
        # Validating function results
        os.dup2(orig_stdout.fileno(), sys.stdout.fileno())
        os.dup2(orig_stdin.fileno(), sys.stdin.fileno())
        try:
            with open("output", "r") as f:
                out_content = f.read()
        except UnicodeDecodeError:
            output(msgs.get_msg("OutputEncodingError", lang), ERROR)
            return

        values_printed = False
        
        if not hide_output:
            output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=out_content)

        try:
            st_out = output_parser(out_content)
            
        except OutputParseError as e:
            output(msgs.get_msg("OutputParseError", lang), INCORRECT, args=arg_presenter(stored_args), inputs=input_presenter(inps), out=out_content, reason=e.msg)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, args=arg_presenter(stored_args), call=call_presenter(func_names[lang], stored_args), inputs=input_presenter(inps))
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inps))
            output(msgs.get_msg("OutputPatternInfo", lang), INFO)
            continue
            
        # The evaluated result must include an object that was changed during the function call
        if result_object_extractor:
            res = result_object_extractor(args, res, st_out)
            
        try: 
            validator(ref, res, st_out)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, args=arg_presenter(stored_args), call=call_presenter(func_names[lang], stored_args), inputs=input_presenter(inps))
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inps))
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, res=res_presenter(res), parsed=parsed_presenter(st_out), output=out_content)
            output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
            values_printed = True
            if error_refs or custom_tests or test_recurrence:
                output(msgs.get_msg("AdditionalTests", lang), INFO)
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
            for test in custom_tests:                
                try: 
                    test(res, st_out, out_content, ref, stored_args, inps)
                except AssertionError as e:
                    output(msgs.get_msg(e, lang, test.__name__), INFO)
            if test_recurrence and (res == prev_res or st_out and st_out == prev_out):
                output(msgs.get_msg("RepeatingResult", lang), INFO)
                
            if info_funcs:
                output(msgs.get_msg("AdditionalInfo", lang), INFO)
                for info_func in info_funcs:
                    output(msgs.get_msg(info_func.__name__, lang), INFO, func_res=info_func(res, st_out, out_content, ref, stored_args, inps))
        else:
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, args=arg_presenter(stored_args), call=call_presenter(func_names[lang], stored_args), inputs=input_presenter(inps))
            if inputs:
                output(msgs.get_msg("PrintInputVector", lang), DEBUG, inputs=input_presenter(inps))
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, res=res_presenter(res), parsed=parsed_presenter(st_out), output=out_content)            
                
            
        if message_validator:
            try: 
                message_validator(out_content, stored_args, inps)
                output(msgs.get_msg("CorrectMessage", lang), CORRECT)
            except AssertionError as e:                
                output(msgs.get_msg(e, lang, "IncorrectMessage"), INCORRECT)
                output(msgs.get_msg("MessageInfo", lang), INFO)
                output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=out_content)
                if not values_printed:
                    output(msgs.get_msg("PrintTestVector", lang), DEBUG, args=arg_presenter(stored_args), call=call_presenter(func_names[lang], stored_args), inputs=input_presenter(inps))
                
        
        prev_res = res
        prev_out = st_out
        if inps:
            os.remove(fn)

    
if __name__ == "__main__":
    st_lib = load_library("testlib")
    print(dir(st_lib))
    print(type(st_lib.simple_add))
        
        
    