import copy
import io
import os
import re
import sys
import random
import matlab.engine
from test_core import *


#def load_m_file(st_m_filename, lang="en", nargout=0, custom_msgs={}, hide_output=True, allow_output=True)

checkcode_context_re = re.compile("^L (?P<line>[0-9]+) \(C (?P<column>[0-9-]+)\):")

function_test_msg_extension = ftme = TranslationDict()
ftme.set_msg("MatlabExecutionError", "en", dict(content="There was an error while executing your Matlab code.\nAdditional information: {emsg}"))
ftme.set_msg("MatlabExecutionError", "fi", dict(content="Matlab-koodisi suorituksessa tapahtui virhe.\nLisätietoja: {emsg}"))
ftme.set_msg("MatlabError", "en", dict(content="There was an error while calling the function.\nError message: {emsg}"))
ftme.set_msg("MatlabError", "fi", dict(content="Funktiota kutsuttaessa tapahtui virhe.\nVirheviesti: {emsg}"))
default_func_test_msgs.update(function_test_msg_extension)

program_test_msg_extension = ptme = TranslationDict()
ptme.set_msg("IncorrectResult", "en", dict(content="The result variable(s) in your script had incorrect value(s)."))
ptme.set_msg("IncorrectResult", "fi", dict(content="Ohjelman tulosmuuttujista yksi tai useampi sisälsi vääriä arvoja."))
ptme.set_msg("PrintStudentResult", "en", dict(content="Result variables in your script:\n{res}"))
ptme.set_msg("PrintStudentResult", "fi", dict(content="Tulosmuuttujien arvot ohjelmassasi:\n{res}"))
ptme.set_msg("PrintReference", "en", dict(content="Expected result variables:\n{ref}"))
ptme.set_msg("PrintReference", "fi", dict(content="Tulosmuuttujien arvojen olisi pitänyt olla:\n{ref}"))
default_program_test_msgs.update(program_test_msg_extension)
             
lint_test_msg_extension = ltme = TranslationDict()
ltme.set_msg("LintMessage", "en", dict(content="Matlab code checker notified about line {line} (column(s) {column}). Explanation: {message}"))
ltme.set_msg("LintMessage", "fi", dict(content="Matlabin tarkistin huomautti rivistä {line} (sarake {column}). Selitys: {message}"))
ltme.set_msg("LintFailMessage", "en", dict(content="Matlab code checker had complaints about the code."))
ltme.set_msg("LintFailMessage", "fi", dict(content="Matlabin tarkistin löysi koodista ongelmia."))
ltme.set_msg("LintSuccess", "en", dict(content="Matlab code checker had no complaints about the code."))
ltme.set_msg("LintSuccess", "fi", dict(content="Matlabin tarkistin ei löytänyt koodista valitettavaa."))
default_lint_test_msgs.update(lint_test_msg_extension)



class ReferenceWorkspace(dict):
    
    def __init__(self, name, **kwargs):
        self.__name__ = name
        super().__init__(self, **kwargs)
        

def default_matlab_call_presenter(func_name, args):
    return ""

def default_script_result_extractor(varnames, workspace, output):
    result = {}
    for var in varnames:
        try:
            value = workspace[var]
        except MatlabExecutionError:
            value = None
        
        result[var] = value
    
    return result

def default_checkcode_parser(output):
    messages = []
    lines = output.split("\n")
    for line in lines:
        match = checkcode_context_re.match(line)
        if match:
            line_no = match.group("line")
            col_no = match.group("column")
            message = line.split(":", 1)[-1]
            messages.append({
                "line": line_no,
                "column": col_no,
                "message": message
            })
        
    return messages

def default_checkcode_validator(evaluation):
    assert not evaluation

def initiate_matlab(st_m_filename):
    """
    
    """
    
    global matlab_eng
    sessions = matlab.engine.find_matlab()
    if sessions:
        matlab_eng = matlab.engine.connect_matlab(random.choice(sessions))
    else:
        matlab_eng = matlab.engine.start_matlab()
    matlab_eng.cd(os.path.dirname(os.path.abspath(st_m_filename)))

def test_matlab_function(st_m_filename, test_vector, ref_func, 
                  lang="en",
                  custom_msgs={},
                  hide_output=True,
                  test_recurrence=True,
                  error_refs=[],
                  custom_tests=[],
                  info_funcs=[],
                  validator=result_validator,
                  presenter=default_presenters,
                  output_parser=default_parser,
                  result_object_extractor=None,
                  argument_cloner=default_argument_cloner,
                  repeat=1,
                  nargout=1,
                  new_test=default_new_test):
    """
    test_matlab_function(st_m_filename, test_vector, ref_func[, lang="en"][, kwarg1][, ...])
    
    """
    
    # One time preparations
    msgs = copy.deepcopy(default_func_test_msgs)
    msgs.update(custom_msgs)
    callable_name = os.path.splitext(st_m_filename)[0]
        
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

    # Call the test vector function (if it is a function)
    if inspect.isfunction(test_vector):
        test_vector = test_vector()
        
    # Show the name of the function
    json_output.new_test(
        msgs.get_msg("FunctionName", lang)["content"].format(name=callable_name)
    )
    
   # Prepare test cases. Each case is comprised of its vectors and the reference result 
    tests = []
    for v in test_vector:
        if inspect.isfunction(ref_func):
            tests.append((v, ref_func(*argument_cloner(v))))
        else:
            tests.append((v, getattr(matlab_eng, ref_func)(*argument_cloner(v))))
    
    prev_res = None
    prev_out = None
    
    # Running tests
    for i, test in enumerate(tests):
        json_output.new_run()
        
        args, ref = test
        new_test(args, [])
        
        # Create objects for stdout and stderr
        o = io.StringIO()
        e = io.StringIO()
        
        stored_args = argument_cloner(args)
        
        # Calling the student function
        try:
            st_func = getattr(matlab_eng, callable_name)
            if isinstance(st_func, matlab.engine.matlabengine.MatlabFunc):
                for i in range(repeat):
                    res = st_func(*args, nargout=nargout, stdout=o, stderr=e)
            else:
                output(msgs.get_msg("IsNotFunction", lang), ERROR, name=callable_name)
                return
        except:
            etype, evalue, etrace = sys.exc_info()
            ename = evalue.__class__.__name__
            emsg = str(evalue)
            output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
                args=arg_presenter(stored_args),
                emsg=emsg,
                ename=ename
            )
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(callable_name, stored_args)
            )
            return
        
        # Check Matlab stderr for errors
        st_err = e.getvalue()
        if st_err:
            # TODO: parse context from error message
            output(msgs.get_msg("MatlabError", lang), ERROR, context="", emsg=st_err)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(callable_name, stored_args)
            )
            continue
        
        # Validating function results
        st_output = o.getvalue()
        values_printed = False
        if not hide_output:
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=st_output)
        
        try:
            st_out = output_parser(st_output)
        except OutputParseError as e:
            output(msgs.get_msg("OutputParseError", lang), INCORRECT,
                args=arg_presenter(stored_args),
                output=st_output,
                reason=str(e)
            )
            output(msgs.get_msg("PrintTestVector", lang), DEBUG, 
                args=arg_presenter(stored_args), 
                call=call_presenter(callable_name, stored_args)
            )
            output(msgs.get_msg("OutputPatternInfo", lang), INFO)
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=st_output)
            continue

        # The evaluated result must include an object that was changed during the function call
        if result_object_extractor:
            res = result_object_extractor(args, res, st_out)
            
        try: 
            validator(ref, res, st_out)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(callable_name, stored_args)
            )
            
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
                res=res_presenter(res),
                parsed=parsed_presenter(st_out),
                output=st_output
            )
            output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
            values_printed = True
            if error_refs or custom_tests or test_recurrence:
                output(msgs.get_msg("AdditionalTests", lang), INFO)
            
            for eref_func in error_refs:
                if inspect.isfunction(eref_func):
                    eref = eref_func(*argument_cloner(args))
                else:
                    eref = getattr(matlab_eng, eref_func)(*argument_cloner(args))
                try: 
                    validator(eref, res, st_out)
                    output(msgs.get_msg(eref_func.__name__, lang), INFO)
                except AssertionError as e:
                    pass
                
            for custom_test in custom_tests:
                try: 
                    custom_test(res, st_out, st_output, ref, stored_args, [])
                except AssertionError as e:
                    output(msgs.get_msg(e, lang, custom_test.__name__), INFO)

            if test_recurrence and (res == prev_res or st_out and st_out == prev_out):
                output(msgs.get_msg("RepeatingResult", lang), INFO)
                
            if info_funcs:
                output(msgs.get_msg("AdditionalInfo", lang), INFO)
                for info_func in info_funcs:
                    try:
                        output(msgs.get_msg(info_func.__name__, lang), INFO,
                            func_res=info_func(res, st_out, st_output, ref, stored_args, [])
                        )
                    except NoAdditionalInfo:
                        pass
                
        else:
            output(msgs.get_msg("PrintTestVector", lang), DEBUG,
                args=arg_presenter(stored_args),
                call=call_presenter(callable_name, stored_args)
            )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, res=res_presenter(res), parsed=parsed_presenter(st_out), output=st_output)
            values_printed = True
            
        prev_res = res
        prev_out = st_out

def test_matlab_script(st_m_filename, resvar_vector, ref_object,
                       lang="en",
                       custom_msgs={},
                       hide_output=True,
                       error_refs=[],
                       custom_tests=[],
                       info_funcs=[],
                       validator=result_validator,
                       presenter=default_presenters,
                       output_parser=default_parser,
                       result_object_extractor=default_script_result_extractor,
                       new_test=default_new_test):
    """
    test_matlab_scriptn(st_m_filename, ref_object[, lang="en"][, kwarg1][, ...])
    """
    
    # One time preparations
    msgs = copy.deepcopy(default_program_test_msgs)
    msgs.update(custom_msgs)
    callable_name = os.path.splitext(st_m_filename)[0]
    
    # Set specific presenters to use generic presenter if not given
    if isinstance(presenter, dict):
        ref_presenter = presenter.get("ref", default_value_presenter)
        res_presenter = presenter.get("res", default_value_presenter)       
        parsed_presenter = presenter.get("parsed", default_value_presenter)
    else:        
        ref_presenter = presenter
        res_presenter = presenter
        parsed_presenter = presenter

    json_output.new_test(
        msgs.get_msg("ProgramName", lang)["content"].format(st_mname=callable_name)
    )
    
    json_output.new_run()
    
    # Create objects for stdout and stderr
    o = io.StringIO()
    e = io.StringIO()
        
    try:
        st_script = getattr(matlab_eng, callable_name)
        st_script(nargout=0, stdout=o, stderr=e)
    except:
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
            emsg=emsg,
            ename=ename
        )
        return
        
    # Check Matlab stderr for errors
    st_err = e.getvalue()
    if st_err:
        # TODO: parse context from error message
        output(msgs.get_msg("MatlabError", lang), ERROR, context="", emsg=st_err)
        output(msgs.get_msg("PrintTestVector", lang), DEBUG,
            args=arg_presenter(stored_args),
            call=call_presenter(callable_name, stored_args)
        )
        return
    
    # Validating function results
    st_output = o.getvalue()
    values_printed = False
    if not hide_output:
        output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=st_output)
    
    try:
        st_out = output_parser(st_output)
    except OutputParseError as e:
        output(msgs.get_msg("OutputParseError", lang), INCORRECT,
            args=arg_presenter(stored_args),
            output=st_output,
            reason=str(e)
        )
        output(msgs.get_msg("OutputPatternInfo", lang), INFO)
        output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=st_output)
        return
    
    res = result_object_extractor(resvar_vector, matlab_eng.workspace, st_out)
    
    try: 
        validator(ref_object, res, st_out)
        output(msgs.get_msg("CorrectResult", lang), CORRECT)
    except AssertionError as e:
        output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
        output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
            res=res_presenter(res),
            parsed=parsed_presenter(st_out),
            output=st_output
        )
        output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref_object))
        values_printed = True
        if error_refs or custom_tests:
            output(msgs.get_msg("AdditionalTests", lang), INFO)
        
        for eref_object in error_refs:
            try: 
                validator(eref_object, res, st_out)
                output(msgs.get_msg(eref_object.__name__, lang), INFO)
            except AssertionError as e:
                pass
            
        for custom_test in custom_tests:
            try: 
                custom_test(res, st_out, st_output, ref, stored_args, [])
            except AssertionError as e:
                output(msgs.get_msg(e, lang, custom_test.__name__), INFO)

        if test_recurrence and (res == prev_res or st_out and st_out == prev_out):
            output(msgs.get_msg("RepeatingResult", lang), INFO)
            
        if info_funcs:
            output(msgs.get_msg("AdditionalInfo", lang), INFO)
            for info_func in info_funcs:
                try:
                    output(msgs.get_msg(info_func.__name__, lang), INFO,
                        func_res=info_func(res, st_out, st_output, ref, stored_args, [])
                    )
                except NoAdditionalInfo:
                    pass
            
    else:
        output(msgs.get_msg("PrintStudentResult", lang), DEBUG, res=res_presenter(res), parsed=parsed_presenter(st_out), output=st_output)
        values_printed = True
    
def matlab_checkcode_test(st_m_filename,
                          lang="en",
                          extra_options=[],
                          validator=default_checkcode_validator,
                          parser=default_checkcode_parser,
                          info_only=False,
                          custom_msgs={}):
    """
    matlab_checkcode_test(st_m_filename[, lang="en"][, kwarg1][, ...])
    """
    
    msgs = copy.deepcopy(default_lint_test_msgs)
    msgs.update(custom_msgs)
    callable_name = os.path.splitext(st_m_filename)[0]
    
    json_output.new_test(msgs.get_msg("LintTest", lang)["content"])
    json_output.new_run()
    
    o = io.StringIO()
    e = io.StringIO()
    
    options = ["-string", "-notok"] + extra_options
    
    try:
        check_output = matlab_eng.checkcode(callable_name, *options, stdout=o, stderr=e)
    except:
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, emsg=emsg, ename=ename)
        return 
    
    #check_output = o.getvalue()
    evaluation = parser(check_output)
    
    try:
        validator(evaluation)
    except AssertionError as e:
        if info_only:
            output(msgs.get_msg(e, lang, "LintFailMessage"), INFO)
        else:
            output(msgs.get_msg(e, lang, "LintFailMessage"), INCORRECT)
    else:
        output(msgs.get_msg("LintSuccess", lang), CORRECT)
    
    output(msgs.get_msg("LintMessagesBegin", lang), INFO)
    
    for msg in evaluation:
        output(msgs.get_msg("LintMessage", lang), INFO, **msg)
    
    
    
    
