
import importlib
import os
import random
import re
import string
import subprocess
import sys
import tempfile
from collections import namedtuple

from test_core import *

reg_pattern = re.compile("%(?P<reg>\S+):\s+(?P<init>0x[0-9a-f]+)\s+(?P<new>0x[0-9a-f]+)")
mem_pattern = re.compile("(?P<addr>0x[0-9a-f]+):\s+(?P<init>0x[0-9a-f]+)\s+(?P<new>0x[0-9a-f]+)")

ptme = program_test_msgs_extension = TranslationDict()
ptme.set_msg("PrintInit", "fi", dict(content="Ohjelman alkuun liitetty alustus:\n{init}"))
ptme.set_msg("PrintInit", "en", dict(content="Initialization attached to the beginning of the program:\n{init}"))
ptme.set_msg("PrintBuildErrors", "fi", dict(content="Ohjelman kääntäminen epäonnistui. Kääntäjän ilmoitukset:\n{errors}"))
ptme.set_msg("PrintBuildErrors", "en", dict(content="Compiling the program failed. Compiler errors:\n{errors}"))
ptme.set_msg("PrintRunErrors", "fi", dict(content="Ohjelmaa suorittaessa tapahtui virhe. Simulaattorin ilmoitukset:\n{errors}"))
ptme.set_msg("PrintRunErrors", "en", dict(content="Running the program failed. Simulator errors:\n{errors}"))
ptme.set_msg("OutputParseError", "fi", dict(content="Ohjelma ei käyttänyt kaikkia tehtävänannon rekisterejä ja muistiosoitteita. Viesti:\n{reason}"))
ptme.set_msg("OutputParseError", "en", dict(content="The program didn't use all the required registers and memory addresses. Message:\n{reason}"))
ptme.set_msg("PrintStudentResult", "fi", dict(content="Tarkistettujen rekisterien muutokset:\n{parsed.regs}\nTarkistettujen muistiosoitteiden muutokset:\n{parsed.mem}"))
ptme.set_msg("PrintStudentResult", "en", dict(content="Changes in relevant registers:\n{ref.regs}\nChanges in relevant memory addresses:\n{ref.mem}"))
ptme.set_msg("PrintReference", "fi", dict(content="Odotetut rekisterien muutokset:\n{ref.regs}\nOdotetut muistiosoitteidein muutokset:\n{ref.mem}"))

default_program_test_msgs.update(ptme)


TestOutput = namedtuple("TestOutput", ["regs", "mem"])

def run_command(command):
    
    stdin = tempfile.TemporaryFile()
    stdout = tempfile.TemporaryFile()
    stderr = tempfile.TemporaryFile()
    
    proc = subprocess.Popen(
        args=command, bufsize=-1, executable=None,
        stdin=stdin, stdout=stdout, stderr=stderr, # Standard fds
        close_fds=True,                            # Don't inherit fds
        shell=False,                               # Don't run in shell        
        universal_newlines=False                   # Binary stdout
    )

    proc.wait(timeout=5)    

    stdout.seek(0)
    stderr.seek(0)
    
    return stdout.read().decode("utf-8"), stderr.read().decode("utf-8")    

def compile_program(program, ext, init):
    with open(program) as stdf:
        content = init + stdf.read()
        
    tempname = program.replace(".ys", "") + ext + ".ys"
    with open(tempname, "w") as stdf:
        stdf.write(content)
        
    args = ["yas", tempname]
    output, errors = run_command(args)
    return errors

def run_program(program, ext):
    args = ["yis", program.replace(".ys", "") + ext + ".yo"]
    output, errors = run_command(args)
    return output, errors

def default_y86_output_parser(output, target_regs, target_mem):
    regdict = {}
    regs = reg_pattern.findall(output)
    for reg, old_v, new_v in regs:
        regdict[reg] = (old_v, new_v)
        
    result_regs = {}
    for treg in target_regs:
        result_regs[treg] = regdict.get(treg, ("0x{:016x}".format(0), "0x{:016x}".format(0)))
        
    memdict = {}
    mem = mem_pattern.findall(output)
    for addr, old_v, new_v in mem:
        memdict[addr] = (old_v, new_v)
        
    result_mem = {}
    for tmem in target_mem:
        result_mem[tmem] = memdict.get(tmem, ("0x{:016x}".format(0), "0x{:016x}".format(0)))

    return result_regs, result_mem

def default_init_presenter(value):
    return "{{{\n" + value + "\n}}}"

def default_y86_presenter(value):
    regs = value[0]
    addrs = value[1]
    
    reg_lines = []
    for reg in regs:
        reg_lines.append("%{}: ".format(reg) + " -> ".join(regs[reg]))
    
    reg_str = "{{{\n" + "\n".join(reg_lines) + "\n}}}"
    
    mem_lines = []
    for addr in addrs:
        mem_lines.append("{}: ".format(addr) + " -> ".join(addrs[addr]))
        
    mem_str = "{{{\n" + "\n".join(mem_lines) + "\n}}}"
    
    return TestOutput(regs=reg_str, mem=mem_str)

default_y86_presenters = {
    "arg": default_init_presenter,
    "res": default_y86_presenter,
    "ref": default_y86_presenter,
}

def test_y86_program(st_program, test_vector, ref_program, lang="en", custom_msgs={}, registers=[], mem_addrs=[], output_parser=default_y86_output_parser, validator=result_validator, presenter=default_y86_presenters, new_test=default_new_test):
    
    msgs = default_program_test_msgs.copy()
    msgs.update(custom_msgs)

    if isinstance(presenter, dict):
        arg_presenter = presenter.get("arg", default_init_presenter)
        ref_presenter = presenter.get("ref", default_y86_presenter)
        res_presenter = presenter.get("res", default_y86_presenter)       
    else:        
        arg_presenter = presenter
        ref_presenter = presenter
        res_presenter = presenter
        
    if inspect.isfunction(test_vector):
        test_vector = test_vector()
        
    json_output.new_test(msgs.get_msg("ProgramName", lang)["content"])
    
    for i, init in enumerate(test_vector):
        
        json_output.new_run()
        new_test([], [])
        
        ref_ext = "_" + "".join(random.sample(string.ascii_lowercase, 10))
        st_ext = "_" + "".join(random.sample(string.ascii_lowercase, 10))
        compile_program(ref_program, ref_ext, init)
        ref_output, ref_errors = run_program(ref_program, ref_ext)
        
        ref = output_parser(ref_output, registers, mem_addrs)
        
        output(msgs.get_msg("PrintInit", lang), DEBUG, init=arg_presenter(init))
        
        st_build_errors = compile_program(st_program, st_ext, init)
        
        if st_build_errors:
            output(msgs.get_msg("PrintBuildErrors", lang), ERROR, errors=st_build_errors)
            return
        
        st_output, st_errors = run_program(st_program, st_ext)
        
        if st_errors:
            output(msgs.get_msg("PrintRunErrors", lang), ERROR, errors=st_errors)
            return
            
        try:
            res = output_parser(st_output, registers, mem_addrs)
        except OutputParseError as e:
            output(msgs.get_msg("OutputParseError", lang), ERROR, reason=str(e))
            continue
        
        try:
            validator(ref, res, None)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, parsed=res_presenter(res))
            output(msgs.get_msg("PrintReference", lang), DEBUG, ref=ref_presenter(ref))
            output(msgs.get_msg("PrintStudentOutput", lang), INFO, output=st_output)  
        else:
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, parsed=res_presenter(res))

def y86_static_test(st_program, lang, validators, info_only=False, custom_msgs={}):
    
    msgs = copy.deepcopy(default_static_test_msgs)
    msgs.update(custom_msgs)
    
    #output(msgs.get_msg("StaticTest", lang).format(fname=func_names.get(lang, "")), INFO)
    json_output.new_test(msgs.get_msg("StaticTest", lang)["content"])
    json_output.new_run()
    
    try:
        with open(st_program) as source_file:
            source = source_file.read()
        
    except:
        etype, evalue, etrace = sys.exc_info()
        ename = evalue.__class__.__name__
        emsg = str(evalue)
        output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR, emsg=emsg, ename=ename)
        return 
        
    failed = 0
    for validator in validators:
        try: 
            validator(source)
        except AssertionError as e:
            if info_only:
                output(msgs.get_msg(e, lang, validator.__name__), INFO)
            else:
                output(msgs.get_msg(e, lang, validator.__name__), ERROR)
                failed += 1
    
    if not failed:
        output(msgs.get_msg("CorrectResult", lang), CORRECT)
    