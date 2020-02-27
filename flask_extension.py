import flask
import flask_sqlalchemy
import flask_restful
import html
import io
import json
import os
import re
import sys
import random
import tempfile
from markdown import Markdown
from sqlalchemy.orm.attributes import InstrumentedAttribute
from test_core import *

class NoFlaskApp(Exception):
    pass

class NoFlaskDb(Exception):
    pass

class RefResponse(object):
    status_code = 0
    data = ""
    parsed_data = ""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            


class GeneratedRequest(object):
    
    def __init__(self, href, method="get", query=None, data=None, extra_kw=None):
        self.href = href
        self.method = method
        self.query = query or []
        self.extra_kw = extra_kw or {}
        self.data = data or []

flask_msgs = TranslationDict()
flask_msgs.set_msg("NoFlaskApp", "fi", dict(content="Moduulista {st_module} ei löytynyt Flask app -objektia."))
flask_msgs.set_msg("NoFlaskApp", "en", dict(content="The module {st_module} did not contain a Flask app object."))
flask_msgs.set_msg("FunctionName", "fi", dict(content="Testataan reittiä {route}..."))
flask_msgs.set_msg("FunctionName", "en", dict(content="Testing route {route}..."))
flask_msgs.set_msg("CorrectResult", "fi", dict(content="Sovelluksen vastaus oli oikea."))
flask_msgs.set_msg("CorrectResult", "en", dict(content="The application's response was correct."))
flask_msgs.set_msg("IncorrectResult", "fi", dict(content="Sovelluksen vastaus oli väärä."))
flask_msgs.set_msg("IncorrectResult", "en", dict(content="The application's response was incorrect."))
flask_msgs.set_msg("PrintTestRequest", "fi", dict(content="Testattu URL: {{{{{{{url}{query}}}}}}}. Testidata:\n{data}"))
flask_msgs.set_msg("PrintTestRequest", "en", dict(content="Tested URL: {{{{{{{url}{query}}}}}}}. Test data:\n{data}"))
flask_msgs.set_msg("PrintDatabase", "fi", dict(content="Tietokannan alkutila:\n{db}"))
flask_msgs.set_msg("PrintDatabase", "en", dict(content="Initial database state:\n{db}"))
flask_msgs.set_msg("PrintStudentResult", "fi", dict(content="Sovelluksen vastaus:\nKoodi: {code}\nArvo(t): {res}"))
flask_msgs.set_msg("PrintStudentResult", "en", dict(content="Application's response\nCode: {code}\nValue(s): {res}"))
flask_msgs.set_msg("PrintStudentOutput", "fi", dict(content="Vastauksen koko sisältö:\n{output}"))
flask_msgs.set_msg("PrintStudentOutput", "en", dict(content="Full response body:\n{output}\n"))
flask_msgs.set_msg("PrintReference", "fi", dict(content="Odotettu vastaus:\nKoodi: {code}\nArvo(t): {ref}"))
flask_msgs.set_msg("PrintReference", "en", dict(content="Expected response:\nCode: {code}\nValue(s): {ref}"))
flask_msgs.set_msg("PrintStderr", "fi", dict(content="Pyyntöä toteuttaessa tapahtui poikkeus:\n{{{{{{\n{stderr}\n}}}}}}"))
flask_msgs.set_msg("PrintStderr", "en", dict(content="An exception occurred while processing the request:\n{{{{{{\n{stderr}\n}}}}}}"))
flask_msgs.set_msg("TestState", "fi", dict(content="Testataan tietokannan tila..."))
flask_msgs.set_msg("TestState", "en", dict(content="Testing database state..."))
flask_msgs.set_msg("CorrectState", "fi", dict(content="Tietokanta oli oikeassa tilassa."))
flask_msgs.set_msg("CorrectState", "en", dict(content="Database state was correct."))
flask_msgs.set_msg("IncorrectState", "fi", dict(content="Tietokanta oli virheellisessä tilassa."))
flask_msgs.set_msg("IncorrectState", "en", dict(content="Database state was incorrect."))
flask_msgs.set_msg("fail_no_model_class", "fi", dict(content="Oikean nimistä malliluokkaa ei löytynyt."))
flask_msgs.set_msg("fail_no_model_class", "en", dict(content="No model class found with the tested name."))
flask_msgs.set_msg("fail_model_class_super", "fi", dict(content="Malliluokka ei periytynyt Model:sta."))
flask_msgs.set_msg("fail_model_class_super", "en", dict(content="Model class wasn't inherited from Model."))
flask_msgs.set_msg("fail_valid_not_added", "fi", dict(content="Tallennettua objektia ei lyötynyt tietokannasta."))
flask_msgs.set_msg("fail_valid_not_added", "en", dict(content="The saved object was not found in the database."))
flask_msgs.set_msg("fail_invalid_added", "fi", dict(content="Virheellinen objekti oli tallentunut."))
flask_msgs.set_msg("fail_invalid_added", "en", dict(content="Invalid object was saved."))
flask_msgs.set_msg("fail_unable_to_query", "fi", dict(content="Tietokantakyselyä ei voitu tehdä."))
flask_msgs.set_msg("fail_unable_to_query", "en", dict(content="Unable to execute database query."))
default_func_test_msgs.update(flask_msgs)


create_db_msgs = TranslationDict()
create_db_msgs.set_msg("InitDB", "fi", dict(content="Alustetaan tietokanta..."))
create_db_msgs.set_msg("InitDB", "en", dict(content="Initializing database..."))
create_db_msgs.set_msg("NoFlaskApp", "fi", dict(content="Moduulista {st_module} ei löytynyt Flask app -objektia."))
create_db_msgs.set_msg("NoFlaskApp", "en", dict(content="The module {st_module} did not contain a Flask app object."))
create_db_msgs.set_msg("NoFlaskDb", "fi", dict(content="Moduulista {st_module} ei löytynyt Flask SQLAlchemy -objektia."))
create_db_msgs.set_msg("NoFlaskDb", "en", dict(content="The module {st_module} did not contain a Flask SQLAlchemy object."))
create_db_msgs.set_msg("DbCreated", "fi", dict(content="Tietokannan luominen onnistui."))
create_db_msgs.set_msg("DbCreated", "en", dict(content="Database creation was successful."))
create_db_msgs.set_msg("GenericErrorMsg", "fi", dict(content="Tietokannan luomisessa tapahtui poikkeus.\n{ename}: {emsg}"))
create_db_msgs.set_msg("GenericErrorMsg", "en", dict(content="An error occurred while creating the database.\n{ename}: {emsg}"))
create_db_msgs.set_msg("PopulateDB", "fi", dict(content="Alustetaan tietokantaan lähtötilanne..."))
create_db_msgs.set_msg("PopulateDB", "en", dict(content="Populating DB...."))
create_db_msgs.set_msg("PopulatingError", "fi", dict(content="Alustus epäonnistui. Tarkista, että mallit vastaavat tehtävänantoa."))
create_db_msgs.set_msg("PopulatingError", "en", dict(content="Populating failed. Check that your model classes match the assignment."))


test_db_msgs = TranslationDict()
test_db_msgs.set_msg("StartDbTest", "fi", dict(content="Testataan luotua tietokantaa..."))
test_db_msgs.set_msg("StartDbTest", "en", dict(content="Testing created database..."))
test_db_msgs.set_msg("ModelError", "fi", dict(content="Malliluokassa oli virhe, joka esti testiobjektien luomisen:\n{emsg}."))
test_db_msgs.set_msg("ModelError", "en", dict(content="An error in the model class prevented creation of test instances:\n{emsg}."))
test_db_msgs.set_msg("CorrectAccept", "fi", dict(content="Tietokanta hyväksyi oikeanlaisen objektin."))
test_db_msgs.set_msg("CorrectAccept", "en", dict(content="The database accepted a valid object."))
test_db_msgs.set_msg("CorrectReject", "fi", dict(content="Tietokanta hylkäsi virheellisen objektin."))
test_db_msgs.set_msg("CorrectReject", "en", dict(content="The database rejected an invalid object."))
test_db_msgs.set_msg("IncorrectAccept", "fi", dict(content="Tietokanta hyväksyi virheellisen objektin."))
test_db_msgs.set_msg("IncorrectAccept", "en", dict(content="The database accepted an invalid object."))
test_db_msgs.set_msg("IncorrectReject", "fi", dict(content="Tietokanta hylkäsi oikeanlaisen objektin."))
test_db_msgs.set_msg("IncorrectReject", "en", dict(content="The database rejected a valid object."))
test_db_msgs.set_msg("RejectReason", "fi", dict(content="Hylkäämisen syy: {reason}"))
test_db_msgs.set_msg("RejectReason", "en", dict(content="Reject reason: {reason}"))
test_db_msgs.set_msg("PrintTestObject", "fi", dict(content="Objektin attribuutit:\n{instance}"))
test_db_msgs.set_msg("PrintTestObject", "en", dict(content="Object attributes:\n{instance}"))

test_model_msgs = TranslationDict()
test_model_msgs.set_msg("StartModelTest", "fi", dict(content="Testataan malliluokan {name} kentät..."))
test_model_msgs.set_msg("StartModelTest", "en", dict(content="Testing model class {name} fields..."))
test_model_msgs.set_msg("CorrectFields", "fi", dict(content="Malliluokassa oli kaikki vaaditut kentät."))
test_model_msgs.set_msg("CorrectFields", "en", dict(content="The model class had all required fields."))
test_model_msgs.set_msg("MissingModel", "fi", dict(content="Malliluokkaa {name} ei löytynyt."))
test_model_msgs.set_msg("MissingModel", "en", dict(content="Model class {name} was not found."))
test_model_msgs.set_msg("NotModel", "fi", dict(content="Luokka {name} ei ollut Model-tyyppiä."))
test_model_msgs.set_msg("NotModel", "en", dict(content="Class {name} was not a Model."))
test_model_msgs.set_msg("MissingFields", "fi", dict(content="Malliluokasta puuttui seuraavat kentät:\n{fields}"))
test_model_msgs.set_msg("MissingFields", "en", dict(content="These fields were missing from the model:\n{fields}"))

apibp_parse_msgs = TranslationDict()
apibp_parse_msgs.set_msg("ParseApiBp", "fi", dict(content="Luetaan API Blueprint dokumentti tiedostosta {apibp}..."))
apibp_parse_msgs.set_msg("ParseApiBp", "en", dict(content="Parsing API Blueprint from file {apibp}..."))
apibp_parse_msgs.set_msg("ParsingError", "fi", dict(content="Lähdetiedoston lukeminen epäonnistui:\n{emsg}"))
apibp_parse_msgs.set_msg("ParsingError", "en", dict(content="Parsing the blueprint file failed:\n{emsg}"))
apibp_parse_msgs.set_msg("ApiParsed", "fi", dict(content="Lukeminen onnistui."))
apibp_parse_msgs.set_msg("ApiParsed", "en", dict(content="Parsing successful."))

doc_test_msgs = TranslationDict()
doc_test_msgs.set_msg("LoadDocument", "fi", dict(content="Luetaan dokumentti..."))
doc_test_msgs.set_msg("LoadDocument", "en", dict(content="Parsing document..."))
doc_test_msgs.set_msg("DocumentTest", "fi", dict(content="Luodaan testit dokumentista..."))
doc_test_msgs.set_msg("DocumentTest", "en", dict(content="Generating tests from document..."))
doc_test_msgs.set_msg("DocumentParsed", "fi", dict(content="Dokumentin parsinta onnistui."))
doc_test_msgs.set_msg("DocumentParsed", "en", dict(content="Document was parsed successfully."))
doc_test_msgs.set_msg("InvalidDocument", "fi", dict(content="Dokumentti oli virheellinen. Syy:\n{emsg}"))
doc_test_msgs.set_msg("InvalidDocument", "en", dict(content="Document was invalid. Reason:\n{emsg}"))
doc_test_msgs.set_msg("ShowDocument", "fi", dict(content="Käsiteltävän dokumentin sisältö:\n{doc}"))
doc_test_msgs.set_msg("ShowDocument", "en", dict(content="Contents of the current document:\n{doc}"))
doc_test_msgs.set_msg("TestTarget", "fi", dict(content="Generoidaan testi kohteesta:\n{keys}"))
doc_test_msgs.set_msg("TestTarget", "en", dict(content="Generating test from:\n{keys}"))
doc_test_msgs.set_msg("NoRequest", "fi", dict(content="Palvelinkutsun generointi annetusta dokumentista ei onnistunut."))
doc_test_msgs.set_msg("NoRequest", "en", dict(content="Unable to generate request from the document."))
doc_test_msgs.set_msg("ExceptionInfo", "fi", dict(content="Palvelinkutsun generointi antoi seuraavan virheviestin:\n{etype}: {emgs}"))
doc_test_msgs.set_msg("ExceptionInfo", "en", dict(content="Request generation reported the following error:\n{etype}: {emgs}"))


def default_client_getter(st_module, st_app):
    return st_app.test_client()

# from http://flask.pocoo.org/docs/1.0/testing/
def client_with_db_getter(st_module, st_app):
    db_fd, st_app.config["DATABASE"] = tempfile.mkstemp()
    st_app.config["TESTING"] = True
    client = st_app.test_client()
    
    with st_app.app_context():
        db = find_db(st_module)
        db.create_all()
        
    return client
        
def default_response_validator(ref, res):
    assert ref.status_code == res.status_code
    assert ref.parsed_data == res.parsed_data

def response_code_validator(ref, res):
    assert ref.status_code == res.status_code

def default_db_populator(st_module, db):
    pass    

def default_route_presenter(value):
    return "{{{" + value.replace("{", "<").replace("}", ">") + "}}}"

def default_query_presenter(value):
    if value:
        return "?" + "&".join("{}={}".format(*pair) for pair in value.items())
    else:
        return ""

def default_database_presenter(value):
    return ""

def default_document_presenter(value):
    if isinstance(value, str):
        return "{{{\n" + value + "\n}}}"
    try:
        return "{{{highlight=json\n" + json.dumps(value, indent=4) + "\n}}}"
    except:
        return "{{{\n" + repr(value) + "\n}}}"

def default_response_presenter(value):
    return value.parsed_data

def default_output_presenter(value):
    content = html.escape(value.decode("utf-8"))
    return "{{{\n" + content + "\n}}}"    

def default_instance_presenter(value):
    content = ""
    for name in dir(value):
        if not name.startswith("_"):
            if isinstance(getattr(value.__class__, name), InstrumentedAttribute):
                attr_value = getattr(value, name)
                if isinstance(attr_value, str):
                    content += "{}: {} (str {})\n".format(name, repr(attr_value), len(attr_value))
                else:
                    content += "{}: {} ({})\n".format(name, repr(attr_value), type(attr_value))
    return "{{{\n" + content + "}}}"

def default_data_parser(response):
    response.parsed_data = response.data.decode("utf-8")


def find_app(st_module):
    for name in dir(st_module):
        if not name.startswith("_"):
            if isinstance(getattr(st_module, name), flask.app.Flask):
                return getattr(st_module, name)
    else:
        raise NoFlaskApp
    
def find_db(st_module):
    for name in dir(st_module):
        if not name.startswith("_"):
            if isinstance(getattr(st_module, name), flask_sqlalchemy.SQLAlchemy):
                return getattr(st_module, name)
    else:
        raise NoFlaskDb
    

flask_presenters = {
    "arg": default_route_presenter,
    "query": default_query_presenter,
    "data": default_value_presenter,
    "db": default_database_presenter,
    "ref": default_response_presenter,
    "res": default_response_presenter,
    "out": default_output_presenter
}

db_presenters = {
}

model_presenters = {
    "fields": default_input_presenter
}

def create_student_database(st_module, db_name, lang="en", db_populator=None):
    """
    
    """
    
    msgs = copy.deepcopy(create_db_msgs)

    json_output.new_test(msgs.get_msg("InitDB", lang)["content"])
    json_output.new_run()
    
    try:
        st_app = find_app(st_module)
    except NoFlaskApp:
        output(msgs.get_msg("NoFlaskApp", lang), ERROR, name=st_module.__name__)
        return

    try:
        st_db = find_db(st_module)
    except NoFlaskDb:
        output(msgs.get_msg("NoFlaskDb", lang), ERROR, name=st_module.__name__)
        return

    #st_app = st_module.Flask("test")
    st_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_name
    #st_db = flask_sqlalchemy.SQLAlchemy(st_app)
    
    with st_app.app_context():
        try:
            st_db.create_all()
        except:
            etype, evalue, etrace = sys.exc_info()
            ename = evalue.__class__.__name__
            emsg = str(evalue)
            output(msgs.get_msg(ename, lang, default="GenericErrorMsg"), ERROR,
                emsg=emsg,
                ename=ename
            )
            return
        
        if db_populator:
            output(msgs.get_msg("PopulateDB", lang), INFO)
            try:
                db_populator(st_module, st_db)
            except:
                output(msgs.get_msg("PopulatingError", lang), ERROR)
                return
            
        output(msgs.get_msg("DbCreated", lang), CORRECT)

def parse_api_blueprint(st_apibp_file, lang,
                        custom_msgs={}):
    """
    
    """

    msgs = copy.deepcopy(apibp_parse_msgs)
    msgs.update(custom_msgs)
    
    json_output.new_test(msgs.get_msg("ParseApiBp", lang)["content"].format(
        apibp=st_apibp_file
    ))    
    json_output.new_run()
    
    err = io.StringIO()
    out = io.StringIO()
    save_e = sys.stderr
    save_o = sys.stdout
    sys.stderr = err
    sys.stdout = out
    
    m = Markdown(extensions=["plueprint"])
    m.set_output_format("apiblueprint")
    
    try:
        with open(st_apibp_file) as f:
            st_apibp = m.convert(f.read())
    except Exception as e:
        sys.stdout = save_o
        sys.stderr = save_e
        output(msgs.get_msg("ParsingError", lang), ERROR, emsg=e)
        return None
    
    sys.stdout = save_o
    sys.stderr = save_e
    output(msgs.get_msg("ApiParsed", lang), CORRECT)
    
    return st_apibp
    

def test_route(st_module, route_names, route_vars, ref_func,
               lang="en",
               request_data=[],
               request_query=[],
               db_clone=None,
               extra_kw=None,
               custom_msgs={},
               client_getter=default_client_getter,
               method="get",
               data_kw="data",
               use_db=False,
               error_refs=[],
               custom_tests=[],
               info_funcs=[],
               data_parser=default_data_parser,
               validator=default_response_validator,
               state_validator=None,
               presenter=flask_presenters,
               result_object_extractor=None):
    """
    
    """
    
    msgs = copy.deepcopy(default_func_test_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        route_presenter = presenter.get("arg", default_route_presenter)
        query_presenter = presenter.get("query", default_query_presenter)
        data_presenter = presenter.get("data", default_value_presenter)
        db_presenter = presenter.get("db", default_database_presenter)
        ref_presenter = presenter.get("ref", default_response_presenter)
        res_presenter = presenter.get("res", default_response_presenter)
        output_presenter = presenter.get("out", default_output_presenter)
    else:
        route_presenter = presenter
        query_presenter = presenter
        data_presenter = presenter
        db_presenter = presenter
        ref_presenter = presenter
        res_presenter = presenter
        output_presenter = presenter

    if inspect.isfunction(route_vars):
        route_vars = route_vars()
        
    json_output.new_test(msgs.get_msg("FunctionName", lang)["content"].format(
        route=route_presenter(route_names[lang])
    ))
        
    try:
        st_app = find_app(st_module)
    except NoFlaskApp:
        output(msgs.get_msg("NoFlaskApp", lang), ERROR, name=st_module.__name__)
        return

    st_client = client_getter(st_module, st_app)
    if use_db:
        st_db = find_db(st_module)
    
    if not request_data:
        request_data = [{}] * len(route_vars)
        
    if not request_query:
        request_query = [{}] * len(route_vars)
    
    if extra_kw is None:
        extra_kw = {}
    
    tests = []
    for v, q, d in zip(route_vars, request_query, request_data):
        tests.append((v, q, d, ref_func(v, q, d, db_clone)))
        
    for i, test in enumerate(tests):
        err = io.StringIO()
        out = io.StringIO()
        save_e = sys.stderr
        save_o = sys.stdout
        sys.stderr = err
        sys.stdout = out
        json_output.new_run()
        args, query, data, ref = test
        extra_kw[data_kw] = data
        try:
            res = getattr(st_client, method)(route_names[lang].format(**args), query_string=query, **extra_kw)
        except Exception as e:
            sys.stdout = save_o
            sys.stderr = save_e
            output(msgs.get_msg("PrintStderr", lang), ERROR, stderr=str(e))
            continue

        sys.stderr = save_e
        sys.stdout = save_o
        data_parser(res)
        values_printed = False
        
        try:
            validator(ref, res)
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
        except AssertionError as e:
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintTestRequest", lang), DEBUG,
                url=route_names[lang].format(**args),
                method=method.upper(),
                query=query_presenter(query),
                data=data_presenter(data)
            )
            if db_clone:
                output(msgs.get_msg("PrintDatabase", lang), DEBUG,
                    db=db_presenter(db_clone)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
                code = res.status_code,
                res=res_presenter(res),
            )
            
            if res.data:
                output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=output_presenter(res.data))
            
            err.seek(0)
            err_contents = err.read()
            if err_contents:
                output(msgs.get_msg("PrintStderr", lang), ERROR, stderr=err_contents)
            
            output(msgs.get_msg("PrintReference", lang), DEBUG,
                   code = ref.status_code,
                   ref=ref_presenter(ref)
            )
            values_printed = True
            if error_refs or custom_tests:
                output(msgs.get_msg("AdditionalTests", lang), INFO)

            for eref_func in error_refs:
                eref_func(args, query, data, db_clone)
                try: 
                    validator(eref, res)
                    output(msgs.get_msg(eref_func.__name__, lang), INFO)
                except AssertionError as e:
                    pass

            for custom_test in custom_tests:
                try: 
                    custom_test(res, ref, args, query, data, db_clone)
                except AssertionError as e:
                    output(msgs.get_msg(e, lang, custom_test.__name__), INFO)

            if info_funcs:
                output(msgs.get_msg("AdditionalInfo", lang), INFO)
                for info_func in info_funcs:
                    try:
                        output(msgs.get_msg(info_func.__name__, lang), INFO,
                            func_res=info_func(res, ref, args, query, data, db_clone)
                        )
                    except NoAdditionalInfo:
                        pass
        else:
            output(msgs.get_msg("PrintTestRequest", lang), DEBUG,
                url=route_names[lang].format(**args),
                method=method.upper(),
                query=query_presenter(query),
                data=data_presenter(data)
            )
            if db_clone:
                output(msgs.get_msg("PrintDatabase", lang), DEBUG,
                    db=db_presenter(db_clone)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
                code = res.status_code,
                res=res_presenter(res),
            )
            if res.data:
                output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=output_presenter(res.data))
            values_printed = True
            
        if use_db and state_validator:
            output(msgs.get_msg("TestState", lang), INFO)  
            try:
                state_validator(st_db, args, query, data, ref)
            except AssertionError as e:
                output(msgs.get_msg(e, lang, "IncorrectState"), INCORRECT)
            else:
                output(msgs.get_msg("CorrectState", lang), CORRECT)
                        
    if use_db:
        st_db.session.remove()
        st_db.drop_all()
                
            
            
            
def test_db_structure(db_handle, app_handle, test_vector,
                      lang="en",
                      custom_msgs={},
                      presenter=db_presenters):
    """
    
    """
    
    msgs = copy.deepcopy(test_db_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        instance_presenter = presenter.get("inst", default_instance_presenter)
    else:
        instance_presenter = presenter
        
    json_output.new_test(msgs.get_msg("StartDbTest", lang)["content"])

    try:
        if inspect.isfunction(test_vector):
            test_vector = test_vector()
    except Exception as e:
        json_output.new_run()
        output(msgs.get_msg("ModelError", lang), ERROR, emsg=str(e))
        return
    
    with app_handle.app_context():
        for test_obj, valid in test_vector:
            json_output.new_run()
            try:
                db_handle.session.add(test_obj)
                db_handle.session.commit()
            except Exception as e:
                if valid:
                    output(msgs.get_msg("IncorrectReject", lang), INCORRECT)
                else:
                    output(msgs.get_msg("CorrectReject", lang), CORRECT)
                output(msgs.get_msg("RejectReason", lang), INFO, reason=str(e))
                db_handle.session.rollback()
            else:
                if valid:
                    output(msgs.get_msg("CorrectAccept", lang), CORRECT)
                else:
                    output(msgs.get_msg("IncorrectAccept", lang), INCORRECT)
            
            output(msgs.get_msg("PrintTestObject", lang), DEBUG,
                   instance=instance_presenter(test_obj)
            )

def test_model(st_module, db_handle, model_name, attr_list, lang="en", custom_msgs={}, presenter=model_presenters):
    msgs = copy.deepcopy(test_model_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        fields_presenter = presenter.get("fields", default_input_presenter)
    else:
        fields_presenter = presenter
    
    json_output.new_test(msgs.get_msg("StartModelTest", lang)["content"].format(name=model_name))
    json_output.new_run()
    
    try:
        model_class = getattr(st_module, model_name)
    except:
        output(msgs.get_msg("MissingModel", lang), INCORRECT, name=model_name)
        return False
        
    if not db_handle.Model in model_class.__bases__:
        output(msgs.get_msg("NotModel", lang), INCORRECT, name=model_name)
        return False
    
    missing = []
    for attr in attr_list:
        if not hasattr(model_class, attr):
            missing.append(attr)
            
    if missing:
        output(msgs.get_msg("MissingFields", lang), INCORRECT, fields=fields_presenter(missing))
        return False
    else:
        output(msgs.get_msg("CorrectFields", lang), CORRECT)
        return True
    
def parse_document(st_doc, lang, doc_parser=json.loads, custom_msgs={}):
    
    msgs = copy.deepcopy(doc_test_msgs)
    msgs.update(custom_msgs)
    
    json_output.new_test(msgs.get_msg("LoadDocument", lang)["content"])
    
    err = io.StringIO()
    out = io.StringIO()
    save_e = sys.stderr
    save_o = sys.stdout
    sys.stderr = err
    sys.stdout = out
    json_output.new_run()
    
    try:
        test_doc = doc_parser(st_doc)
    except Exception as e:
        sys.stdout = save_o
        sys.stderr = save_e
        output(msgs.get_msg("InvalidDocument", lang), ERROR, emsg=e)
        return None

    output(msgs.get_msg("DocumentParsed", lang), CORRECT)

    sys.stdout = save_o
    sys.stderr = save_e
    
    return test_doc

    
def test_from_document(test_doc, target_module, request_driver,
                       lang="en",
                       doc_parser=json.loads,
                       custom_msgs={},
                       db_clone=None,
                       use_db=False,
                       validator=default_response_validator,
                       presenter=flask_presenters,
                       data_parser=default_data_parser,
                       client_getter=default_client_getter
                   
                   
                   
                   ):
    """
    
    """
    
    msgs = copy.deepcopy(default_func_test_msgs)
    msgs.update(doc_test_msgs)
    msgs.update(custom_msgs)
    
    if isinstance(presenter, dict):
        route_presenter = presenter.get("arg", default_route_presenter)
        query_presenter = presenter.get("query", default_query_presenter)
        data_presenter = presenter.get("data", default_value_presenter)
        db_presenter = presenter.get("db", default_database_presenter)
        ref_presenter = presenter.get("ref", default_response_presenter)
        res_presenter = presenter.get("res", default_response_presenter)
        output_presenter = presenter.get("out", default_output_presenter)
        doc_presenter = presenter.get("doc", default_document_presenter)
    else:
        route_presenter = presenter
        query_presenter = presenter
        data_presenter = presenter
        db_presenter = presenter
        ref_presenter = presenter
        res_presenter = presenter
        output_presenter = presenter
        doc_presenter = presenter
    
    target_client = client_getter(target_module, target_module.app)

    json_output.new_test(msgs.get_msg("DocumentTest", lang)["content"])
    
    save_e = sys.stderr
    save_o = sys.stdout

    for doc, msg_key, req, ref in request_driver(test_doc, target_module, db_clone):
        err = io.StringIO()
        out = io.StringIO()

        json_output.new_run()
        
        output(msgs.get_msg("ShowDocument", lang), INFO, doc=doc_presenter(doc))
        output(msgs.get_msg(msg_key, lang, "TestTarget"), INFO, **ref.__dict__)
        
        if req is None:
            output(msgs.get_msg("NoRequest", lang), ERROR)
            continue
        elif isinstance(req, Exception):
            output(msgs.get_msg("NoRequest", lang), ERROR)
            output(msgs.get_msg("ExceptionInfo", lang), DEBUG, etype=req.__class__.__name__, emgs=req)
            continue

        sys.stderr = err
        sys.stdout = out

        try:
            res = getattr(target_client, req.method)(req.href, query_string=req.query, **req.extra_kw)
        except Exception as e:
            sys.stdout = save_o
            sys.stderr = save_e
            output(msgs.get_msg("PrintStderr", lang), ERROR, stderr=str(e))
            continue
            
        data_parser(res)

        sys.stdout = save_o
        sys.stderr = save_e

        try:
            validator(ref, res)
        except AssertionError as e:
            output(msgs.get_msg(e, lang, "IncorrectResult"), INCORRECT)
            output(msgs.get_msg("PrintTestRequest", lang), DEBUG,
                url=req.href,
                method=req.method.upper(),
                query=query_presenter(req.query),
                data=data_presenter(req.data)
            )
            if db_clone:
                output(msgs.get_msg("PrintDatabase", lang), DEBUG,
                    db=db_presenter(db_clone)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG,
                code = res.status_code,
                res=res_presenter(res),
            )
            if res.data:
                output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=output_presenter(res.data))

            err.seek(0)
            err_contents = err.read()
            if err_contents:
                output(msgs.get_msg("PrintStderr", lang), ERROR, stderr=err_contents)

            output(msgs.get_msg("PrintReference", lang), DEBUG,
                   code = ref.status_code,
                   ref=ref_presenter(ref)
            )
        else:
            output(msgs.get_msg("CorrectResult", lang), CORRECT)
            output(msgs.get_msg("PrintTestRequest", lang), DEBUG,
                url=req.href,
                method=req.method.upper(),
                query=query_presenter(req.query),
                data=data_presenter(req.data)
            )
            if db_clone:
                output(msgs.get_msg("PrintDatabase", lang), DEBUG,
                    db=db_presenter(db_clone)
                )
            output(msgs.get_msg("PrintStudentResult", lang), DEBUG, 
                code = res.status_code,
                res=res_presenter(res),
            )
            if res.data:
                output(msgs.get_msg("PrintStudentOutput", lang), DEBUG, output=output_presenter(res.data))

    if use_db:
        target_db = find_db(target_module)
        target_db.session.remove()
        target_db.drop_all()

        
    
        
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    