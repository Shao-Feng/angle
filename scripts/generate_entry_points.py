#!/usr/bin/python2
#
# Copyright 2017 The ANGLE Project Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# generate_entry_points.py:
#   Generates the OpenGL bindings and entry point layers for ANGLE.
#   NOTE: don't run this script directly. Run scripts/run_code_generation.py.

import sys, os, pprint, json
from datetime import date
import registry_xml

# List of GLES1 extensions for which we don't need to add Context.h decls.
gles1_no_context_decl_extensions = [
    "GL_OES_framebuffer_object",
]

# List of GLES1 API calls that have had their semantics changed in later GLES versions, but the
# name was kept the same
gles1_overloaded = [
    "glGetPointerv",
]

# This is a list of exceptions for entry points which don't want to have
# the EVENT macro. This is required for some debug marker entry points.
no_event_marker_exceptions_list = sorted([
    "glPushGroupMarkerEXT",
    "glPopGroupMarkerEXT",
    "glInsertEventMarkerEXT",
])

# Strip these suffixes from Context entry point names. NV is excluded (for now).
strip_suffixes = ["ANGLE", "EXT", "KHR", "OES", "CHROMIUM", "OVR"]

template_entry_point_header = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// entry_points_gles_{annotation_lower}_autogen.h:
//   Defines the GLES {comment} entry points.

#ifndef LIBGLESV2_ENTRY_POINTS_GLES_{annotation_upper}_AUTOGEN_H_
#define LIBGLESV2_ENTRY_POINTS_GLES_{annotation_upper}_AUTOGEN_H_

{includes}

namespace gl
{{
{entry_points}
}}  // namespace gl

#endif  // LIBGLESV2_ENTRY_POINTS_GLES_{annotation_upper}_AUTOGEN_H_
"""

template_entry_point_source = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// entry_points_gles_{annotation_lower}_autogen.cpp:
//   Defines the GLES {comment} entry points.

{includes}

namespace gl
{{
{entry_points}}}  // namespace gl
"""

template_entry_points_enum_header = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// entry_points_enum_autogen.h:
//   Defines the GLES entry points enumeration.

#ifndef LIBGLESV2_ENTRYPOINTSENUM_AUTOGEN_H_
#define LIBGLESV2_ENTRYPOINTSENUM_AUTOGEN_H_

namespace gl
{{
enum class EntryPoint
{{
{entry_points_list}
}};
}}  // namespace gl
#endif  // LIBGLESV2_ENTRY_POINTS_ENUM_AUTOGEN_H_
"""

template_libgles_entry_point_source = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// libGLESv2.cpp: Implements the exported OpenGL ES functions.

{includes}
extern "C" {{
{entry_points}
}} // extern "C"
"""

template_entry_point_decl = """ANGLE_EXPORT {return_type}GL_APIENTRY {name}{explicit_context_suffix}({explicit_context_param}{explicit_context_comma}{params});"""

template_entry_point_def = """{return_type}GL_APIENTRY {name}{explicit_context_suffix}({explicit_context_param}{explicit_context_comma}{params})
{{
    ANGLE_SCOPED_GLOBAL_LOCK();
    {event_comment}EVENT("({format_params})"{comma_if_needed}{pass_params});

    Context *context = {context_getter};
    if (context)
    {{{assert_explicit_context}{packed_gl_enum_conversions}
        if (context->skipValidation() || Validate{name}({validate_params}))
        {{
            {return_if_needed}context->{name_lower_no_suffix}({internal_params});
        }}
    }}
{default_return_if_needed}}}
"""

context_gles_header = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Context_gles_{annotation_lower}_autogen.h: Creates a macro for interfaces in Context.

#ifndef ANGLE_CONTEXT_GLES_{annotation_upper}_AUTOGEN_H_
#define ANGLE_CONTEXT_GLES_{annotation_upper}_AUTOGEN_H_

#define ANGLE_GLES1_CONTEXT_API \\
{interface}

#endif // ANGLE_CONTEXT_API_{annotation_upper}_AUTOGEN_H_
"""

context_gles_decl = """    {return_type} {name_lower_no_suffix}({internal_params}); \\"""

libgles_entry_point_def = """{return_type}GL_APIENTRY gl{name}{explicit_context_suffix}({explicit_context_param}{explicit_context_comma}{params})
{{
    return gl::{name}{explicit_context_suffix}({explicit_context_internal_param}{explicit_context_comma}{internal_params});
}}
"""

template_glext_explicit_context_inc = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// gl{version}ext_explicit_context_autogen.inc:
//   Function declarations for the EGL_ANGLE_explicit_context extension

{function_pointers}
#ifdef GL_GLEXT_PROTOTYPES
{function_prototypes}
#endif
"""

template_glext_function_pointer = """typedef {return_type}(GL_APIENTRYP PFN{name_upper}{explicit_context_suffix_upper}PROC)({explicit_context_param}{explicit_context_comma}{params});"""
template_glext_function_prototype = """{apicall} {return_type}GL_APIENTRY {name}{explicit_context_suffix}({explicit_context_param}{explicit_context_comma}{params});"""

template_validation_header = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {data_source_name}.
//
// Copyright {year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// validationES{annotation}_autogen.h:
//   Validation functions for the OpenGL ES {comment} entry points.

#ifndef LIBANGLE_VALIDATION_ES{annotation}_AUTOGEN_H_
#define LIBANGLE_VALIDATION_ES{annotation}_AUTOGEN_H_

#include "common/PackedEnums.h"

namespace gl
{{
class Context;

{prototypes}
}}  // namespace gl

#endif  // LIBANGLE_VALIDATION_ES{annotation}_AUTOGEN_H_
"""

static_cast_to_dict = {
    "GLintptr": "unsigned long long",
    "GLsizeiptr": "unsigned long long",
    "GLuint64": "unsigned long long",
}

reinterpret_cast_to_dict = {
    "GLsync": "uintptr_t",
    "GLDEBUGPROC": "uintptr_t",
    "GLDEBUGPROCKHR": "uintptr_t",
    "GLeglImageOES": "uintptr_t",
}

format_dict = {
    "GLbitfield": "0x%X",
    "GLboolean": "%u",
    "GLclampx": "0x%X",
    "GLenum": "0x%X",
    "GLfixed": "0x%X",
    "GLfloat": "%f",
    "GLint": "%d",
    "GLintptr": "%llu",
    "GLshort": "%d",
    "GLsizei": "%d",
    "GLsizeiptr": "%llu",
    "GLsync": "0x%016\" PRIxPTR \"",
    "GLubyte": "%d",
    "GLuint": "%u",
    "GLuint64": "%llu",
    "GLDEBUGPROC": "0x%016\" PRIxPTR \"",
    "GLDEBUGPROCKHR": "0x%016\" PRIxPTR \"",
    "GLeglImageOES": "0x%016\" PRIxPTR \"",
}

template_header_includes = """#include <GLES{major}/gl{major}{minor}.h>
#include <export.h>"""

template_sources_includes = """#include "libGLESv2/entry_points_gles_{}_autogen.h"

#include "libANGLE/Context.h"
#include "libANGLE/Context.inl.h"
#include "libANGLE/validationES{}{}.h"
#include "libGLESv2/entry_points_utils.h"
#include "libGLESv2/global_state.h"
"""

template_event_comment = """// Don't run an EVENT() macro on the EXT_debug_marker entry points.
    // It can interfere with the debug events being set by the caller.
    // """

template_validation_proto = "bool Validate%s(%s);"

template_windows_def_file = """; GENERATED FILE - DO NOT EDIT.
; Generated by {script_name} using data from {data_source_name}.
;
; Copyright {year} The ANGLE Project Authors. All rights reserved.
; Use of this source code is governed by a BSD-style license that can be
; found in the LICENSE file.
LIBRARY {lib}
EXPORTS
{exports}
"""

def script_relative(path):
    return os.path.join(os.path.dirname(sys.argv[0]), path)

with open(script_relative('entry_point_packed_gl_enums.json')) as f:
    cmd_packed_gl_enums = json.loads(f.read())

def format_entry_point_decl(cmd_name, proto, params, is_explicit_context):
    comma_if_needed = ", " if len(params) > 0 else ""
    return template_entry_point_decl.format(
        name = cmd_name[2:],
        return_type = proto[:-len(cmd_name)],
        params = ", ".join(params),
        comma_if_needed = comma_if_needed,
        explicit_context_suffix = "ContextANGLE" if is_explicit_context else "",
        explicit_context_param = "GLeglContext ctx" if is_explicit_context else "",
        explicit_context_comma = ", " if is_explicit_context and len(params) > 0 else "")

def type_name_sep_index(param):
    space = param.rfind(" ")
    pointer = param.rfind("*")
    return max(space, pointer)

def just_the_type(param):
    if "*" in param:
        return param[:type_name_sep_index(param) + 1]
    return param[:type_name_sep_index(param)]

def just_the_name(param):
    return param[type_name_sep_index(param)+1:]

def make_param(param_type, param_name):
    return param_type + " " + param_name

def just_the_type_packed(param, entry):
    name = just_the_name(param)
    if entry.has_key(name):
        return entry[name]
    else:
        return just_the_type(param)

def just_the_name_packed(param, reserved_set):
    name = just_the_name(param)
    if name in reserved_set:
        return name + 'Packed'
    else:
        return name

def param_print_argument(param):
    name_only = just_the_name(param)
    type_only = just_the_type(param)

    if "*" in param:
        return "(uintptr_t)" + name_only

    if type_only in reinterpret_cast_to_dict:
        return "(" + reinterpret_cast_to_dict[type_only] + ")" + name_only

    if type_only in static_cast_to_dict:
        return "static_cast<" + static_cast_to_dict[type_only] + ">(" + name_only + ")"

    return name_only

def param_format_string(param):
    if "*" in param:
        return param + " = 0x%016\" PRIxPTR \""
    else:
        type_only = just_the_type(param)
        if type_only not in format_dict:
            raise Exception(type_only + " is not a known type in 'format_dict'")

        return param + " = " + format_dict[type_only]

def default_return_value(cmd_name, return_type):
    if return_type == "void":
        return ""
    return "GetDefaultReturnValue<EntryPoint::" + cmd_name[2:] + ", " + return_type + ">()"

def get_context_getter_function(cmd_name, is_explicit_context):
    if cmd_name == "glGetError" or cmd_name == "glGetGraphicsResetStatusEXT":
        return "GetGlobalContext()"
    elif is_explicit_context:
        return "static_cast<gl::Context *>(ctx)"
    else:
        return "GetValidGlobalContext()"

def format_entry_point_def(cmd_name, proto, params, is_explicit_context):
    packed_gl_enums = cmd_packed_gl_enums.get(cmd_name, {})
    internal_params = [just_the_name_packed(param, packed_gl_enums) for param in params]
    packed_gl_enum_conversions = []
    for param in params:
        name = just_the_name(param)
        if name in packed_gl_enums:
            internal_name = name + "Packed"
            internal_type = packed_gl_enums[name]
            packed_gl_enum_conversions += ["\n        " + internal_type + " " + internal_name +" = FromGLenum<" +
                                          internal_type + ">(" + name + ");"]

    pass_params = [param_print_argument(param) for param in params]
    format_params = [param_format_string(param) for param in params]
    return_type = proto[:-len(cmd_name)]
    default_return = default_return_value(cmd_name, return_type.strip())
    event_comment = template_event_comment if cmd_name in no_event_marker_exceptions_list else ""
    name_lower_no_suffix = cmd_name[2:3].lower() + cmd_name[3:]

    for suffix in strip_suffixes:
        if name_lower_no_suffix.endswith(suffix):
            name_lower_no_suffix = name_lower_no_suffix[0:-len(suffix)]

    return template_entry_point_def.format(
        name = cmd_name[2:],
        name_lower_no_suffix = name_lower_no_suffix,
        return_type = return_type,
        params = ", ".join(params),
        internal_params = ", ".join(internal_params),
        packed_gl_enum_conversions = "".join(packed_gl_enum_conversions),
        pass_params = ", ".join(pass_params),
        comma_if_needed = ", " if len(params) > 0 else "",
        validate_params = ", ".join(["context"] + internal_params),
        format_params = ", ".join(format_params),
        return_if_needed = "" if default_return == "" else "return ",
        default_return_if_needed = "" if default_return == "" else "\n    return " + default_return + ";\n",
        context_getter = get_context_getter_function(cmd_name, is_explicit_context),
        event_comment = event_comment,
        explicit_context_suffix = "ContextANGLE" if is_explicit_context else "",
        explicit_context_param = "GLeglContext ctx" if is_explicit_context else "",
        explicit_context_comma = ", " if is_explicit_context and len(params) > 0 else "",
        assert_explicit_context = "\nASSERT(context == GetValidGlobalContext());"
            if is_explicit_context else "")

def get_internal_params(cmd_name, params):
    packed_gl_enums = cmd_packed_gl_enums.get(cmd_name, {})
    return ", ".join([make_param(just_the_type_packed(param, packed_gl_enums),
                                 just_the_name_packed(param, packed_gl_enums)) for param in params])

def format_context_gles_decl(cmd_name, proto, params):
    internal_params = get_internal_params(cmd_name, params)

    return_type = proto[:-len(cmd_name)]
    name_lower_no_suffix = cmd_name[2:3].lower() + cmd_name[3:]

    for suffix in strip_suffixes:
        if name_lower_no_suffix.endswith(suffix):
            name_lower_no_suffix = name_lower_no_suffix[0:-len(suffix)]

    return context_gles_decl.format(
        return_type = return_type,
        name_lower_no_suffix = name_lower_no_suffix,
        internal_params = internal_params)

def format_libgles_entry_point_def(cmd_name, proto, params, is_explicit_context):
    internal_params = [just_the_name(param) for param in params]
    return_type = proto[:-len(cmd_name)]

    return libgles_entry_point_def.format(
        name = cmd_name[2:],
        return_type = return_type,
        params = ", ".join(params),
        internal_params = ", ".join(internal_params),
        explicit_context_suffix = "ContextANGLE" if is_explicit_context else "",
        explicit_context_param = "GLeglContext ctx" if is_explicit_context else "",
        explicit_context_comma = ", " if is_explicit_context and len(params) > 0 else "",
        explicit_context_internal_param = "ctx" if is_explicit_context else "")

def format_validation_proto(cmd_name, params):
    internal_params = get_internal_params(cmd_name, ["Context *context"] + params)
    return template_validation_proto % (cmd_name[2:], internal_params)

def path_to(folder, file):
    return os.path.join(script_relative(".."), "src", folder, file)

def get_entry_points(all_commands, gles_commands, is_explicit_context):
    decls = []
    defs = []
    export_defs = []
    validation_protos = []

    for command in all_commands:
        proto = command.find('proto')
        cmd_name = proto.find('name').text

        if cmd_name not in gles_commands:
            continue

        param_text = ["".join(param.itertext()) for param in command.findall('param')]
        proto_text = "".join(proto.itertext())
        decls.append(format_entry_point_decl(cmd_name, proto_text, param_text,
            is_explicit_context))
        defs.append(format_entry_point_def(cmd_name, proto_text, param_text, is_explicit_context))

        export_defs.append(format_libgles_entry_point_def(cmd_name, proto_text, param_text,
            is_explicit_context))

        validation_protos.append(format_validation_proto(cmd_name, param_text))

    return decls, defs, export_defs, validation_protos

def get_gles1_decls(all_commands, gles_commands):
    decls = []
    for command in all_commands:
        proto = command.find('proto')
        cmd_name = proto.find('name').text

        if cmd_name not in gles_commands:
            continue

        if cmd_name in gles1_overloaded:
            continue

        param_text = ["".join(param.itertext()) for param in command.findall('param')]
        proto_text = "".join(proto.itertext())
        decls.append(format_context_gles_decl(cmd_name, proto_text, param_text))

    return decls

def get_glext_decls(all_commands, gles_commands, version, is_explicit_context):
    glext_ptrs = []
    glext_protos = []
    is_gles1 = False

    if(version == ""):
        is_gles1 = True

    for command in all_commands:
        proto = command.find('proto')
        cmd_name = proto.find('name').text

        if cmd_name not in gles_commands:
            continue

        param_text = ["".join(param.itertext()) for param in command.findall('param')]
        proto_text = "".join(proto.itertext())

        return_type = proto_text[:-len(cmd_name)]
        params = ", ".join(param_text)

        format_params = {
            "apicall": "GL_API" if is_gles1 else "GL_APICALL",
            "name": cmd_name,
            "name_upper": cmd_name.upper(),
            "return_type": return_type,
            "params": params,
            "explicit_context_comma": ", " if is_explicit_context and len(params) > 0 else "",
            "explicit_context_suffix": "ContextANGLE" if is_explicit_context else "",
            "explicit_context_suffix_upper": "CONTEXTANGLE" if is_explicit_context else "",
            "explicit_context_param": "GLeglContext ctx" if is_explicit_context else ""}

        glext_ptrs.append(template_glext_function_pointer.format(
            **format_params))
        glext_protos.append(template_glext_function_prototype.format(
            **format_params))

    return glext_ptrs, glext_protos

def write_file(annotation, comment, template, entry_points, suffix, includes, file):
    content = template.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = file,
        year = date.today().year,
        annotation_lower = annotation.lower(),
        annotation_upper = annotation.upper(),
        comment = comment,
        includes = includes,
        entry_points = entry_points)

    path = path_to("libGLESv2", "entry_points_gles_{}_autogen.{}".format(
        annotation.lower(), suffix))

    with open(path, "w") as out:
        out.write(content)
        out.close()

def write_export_files(entry_points, includes):
    content = template_libgles_entry_point_source.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = "gl.xml and gl_angle_ext.xml",
        year = date.today().year,
        includes = includes,
        entry_points = entry_points)

    path = path_to("libGLESv2", "libGLESv2_autogen.cpp")

    with open(path, "w") as out:
        out.write(content)
        out.close()

def write_context_api_decls(annotation, template, decls):
    interface_lines = []

    for i in decls['core']:
        interface_lines.append(i)

    for extname in sorted(decls['exts'].keys()):
        interface_lines.append("    /* " + extname + " */ \\")
        interface_lines.extend(decls['exts'][extname])

    content = template.format(
        annotation_lower = annotation.lower(),
        annotation_upper = annotation.upper(),
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = "gl.xml",
        year = date.today().year,
        interface = "\n".join(interface_lines))

    path = path_to("libANGLE", "Context_gles_%s_autogen.h" % annotation.lower())

    with open(path, "w") as out:
        out.write(content)
        out.close()

def write_glext_explicit_context_inc(version, ptrs, protos):
    folder_version = version if version != "31" else "3"

    content = template_glext_explicit_context_inc.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = "gl.xml and gl_angle_ext.xml",
        year = date.today().year,
        version = version,
        function_pointers = ptrs,
        function_prototypes = protos)

    path = os.path.join(script_relative(".."), "include", "GLES{}".format(folder_version),
        "gl{}ext_explicit_context_autogen.inc".format(version))

    with open(path, "w") as out:
        out.write(content)
        out.close()

def write_validation_header(annotation, comment, protos):
    content = template_validation_header.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = "gl.xml and gl_angle_ext.xml",
        year = date.today().year,
        annotation = annotation,
        comment = comment,
        prototypes = "\n".join(protos))

    path = path_to("libANGLE", "validationES%s_autogen.h" % annotation)

    with open(path, "w") as out:
        out.write(content)
        out.close()

def write_windows_def_file(data_source_name, lib, exports):

    content = template_windows_def_file.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = data_source_name,
        exports = "\n".join(exports),
        year = date.today().year,
        lib = lib)

    path = path_to(lib, "%s_autogen.def" % lib)

    with open(path, "w") as out:
        out.write(content)
        out.close()

def get_exports(commands, fmt = None):
    if fmt:
        return ["    %s" % fmt(cmd) for cmd in sorted(commands)]
    else:
        return ["    %s" % cmd for cmd in sorted(commands)]

# Get EGL exports
def get_egl_exports():

    egl = registry_xml.RegistryXML('egl.xml', 'egl_angle_ext.xml')
    exports = []

    capser = lambda fn: "EGL_" + fn[3:]

    for major, minor in [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5]]:
        annotation = "{}_{}".format(major, minor)
        name_prefix = "EGL_VERSION_"

        feature_name = "{}{}".format(name_prefix, annotation)

        egl.AddCommands(feature_name, annotation)

        commands = egl.commands[annotation]

        if len(commands) == 0:
            continue

        exports.append("\n    ; EGL %d.%d" % (major, minor))
        exports += get_exports(commands, capser)

    egl.AddExtensionCommands(registry_xml.supported_egl_extensions, ['egl'])

    for extension_name, ext_cmd_names in sorted(egl.ext_data.iteritems()):

        if len(ext_cmd_names) == 0:
            continue

        exports.append("\n    ; %s" % extension_name)
        exports += get_exports(ext_cmd_names, capser)

    return exports

def main():

    # auto_script parameters.
    if len(sys.argv) > 1:
        inputs = [
            'egl.xml',
            'egl_angle_ext.xml',
            'entry_point_packed_gl_enums.json',
            'gl.xml',
            'gl_angle_ext.xml',
            'registry_xml.py',
        ]
        outputs = [
            '../src/libANGLE/Context_gles_1_0_autogen.h',
            '../src/libANGLE/validationES1_autogen.h',
            '../src/libANGLE/validationES2_autogen.h',
            '../src/libANGLE/validationES31_autogen.h',
            '../src/libANGLE/validationES3_autogen.h',
            '../src/libANGLE/validationESEXT_autogen.h',
            '../src/libGLESv2/entry_points_enum_autogen.h',
            '../src/libGLESv2/entry_points_gles_1_0_autogen.cpp',
            '../src/libGLESv2/entry_points_gles_1_0_autogen.h',
            '../src/libGLESv2/entry_points_gles_2_0_autogen.cpp',
            '../src/libGLESv2/entry_points_gles_2_0_autogen.h',
            '../src/libGLESv2/entry_points_gles_3_0_autogen.cpp',
            '../src/libGLESv2/entry_points_gles_3_0_autogen.h',
            '../src/libGLESv2/entry_points_gles_3_1_autogen.cpp',
            '../src/libGLESv2/entry_points_gles_3_1_autogen.h',
            '../src/libGLESv2/entry_points_gles_ext_autogen.cpp',
            '../src/libGLESv2/entry_points_gles_ext_autogen.h',
            '../src/libGLESv2/libGLESv2_autogen.cpp',
            '../src/libGLESv2/libGLESv2_autogen.def',
        ]

        if sys.argv[1] == 'inputs':
            print ','.join(inputs)
        elif sys.argv[1] == 'outputs':
            print ','.join(outputs)
        else:
            print('Invalid script parameters')
            return 1
        return 0

    gles1decls = {}

    gles1decls['core'] = []
    gles1decls['exts'] = {}

    libgles_ep_defs = []
    libgles_ep_exports = []

    xml = registry_xml.RegistryXML('gl.xml', 'gl_angle_ext.xml')

    # First run through the main GLES entry points.  Since ES2+ is the primary use
    # case, we go through those first and then add ES1-only APIs at the end.
    for major_version, minor_version in [[2, 0], [3, 0], [3, 1], [1, 0]]:
        annotation = "{}_{}".format(major_version, minor_version)
        name_prefix = "GL_ES_VERSION_"

        is_gles1 = major_version == 1
        if is_gles1:
            name_prefix = "GL_VERSION_ES_CM_"

        comment = annotation.replace("_", ".")
        feature_name = "{}{}".format(name_prefix, annotation)

        xml.AddCommands(feature_name, annotation)

        gles_commands = xml.commands[annotation]
        all_commands = xml.all_commands

        decls, defs, libgles_defs, validation_protos = get_entry_points(
            all_commands, gles_commands, False)

        # Write the version as a comment before the first EP.
        libgles_defs.insert(0, "\n// OpenGL ES %s" % comment)
        libgles_ep_exports.append("\n    ; OpenGL ES %s" % comment)

        libgles_ep_defs += libgles_defs
        libgles_ep_exports += get_exports(gles_commands)

        major_if_not_one = major_version if major_version != 1 else ""
        minor_if_not_zero = minor_version if minor_version != 0 else ""

        header_includes = template_header_includes.format(
            major=major_if_not_one, minor=minor_if_not_zero)

        # We include the platform.h header since it undefines the conflicting MemoryBarrier macro.
        if major_version == 3 and minor_version == 1:
            header_includes += "\n#include \"common/platform.h\"\n"

        source_includes = template_sources_includes.format(
            annotation.lower(), major_version, minor_if_not_zero)

        write_file(annotation, comment, template_entry_point_header,
                   "\n".join(decls), "h", header_includes, "gl.xml")
        write_file(annotation, comment, template_entry_point_source,
                   "\n".join(defs), "cpp", source_includes, "gl.xml")
        if is_gles1:
            gles1decls['core'] = get_gles1_decls(all_commands, gles_commands)

        validation_annotation = "%s%s" % (major_version, minor_if_not_zero)
        write_validation_header(validation_annotation, comment, validation_protos)


    # After we finish with the main entry points, we process the extensions.
    extension_defs = []
    extension_decls = []

    # Accumulated validation prototypes.
    ext_validation_protos = []

    for gles1ext in registry_xml.gles1_extensions:
        gles1decls['exts'][gles1ext] = []

    xml.AddExtensionCommands(registry_xml.supported_extensions, ['gles2', 'gles1'])

    for extension_name, ext_cmd_names in sorted(xml.ext_data.iteritems()):

        # Detect and filter duplicate extensions.
        decls, defs, libgles_defs, validation_protos = get_entry_points(
            xml.all_commands, ext_cmd_names, False)

        # Avoid writing out entry points defined by a prior extension.
        for dupe in xml.ext_dupes[extension_name]:
            msg = "// {} is already defined.\n".format(dupe[2:])
            defs.append(msg)

        # Write the extension name as a comment before the first EP.
        comment = "\n// {}".format(extension_name)
        defs.insert(0, comment)
        decls.insert(0, comment)
        libgles_defs.insert(0, comment)
        libgles_ep_exports.append("\n    ; %s" % extension_name)

        extension_defs += defs
        extension_decls += decls

        ext_validation_protos += [comment] + validation_protos

        libgles_ep_defs += libgles_defs
        libgles_ep_exports += get_exports(ext_cmd_names)

        if extension_name in registry_xml.gles1_extensions:
            if extension_name not in gles1_no_context_decl_extensions:
                gles1decls['exts'][extension_name] = get_gles1_decls(all_commands, ext_cmd_names)

    # Special handling for EGL_ANGLE_explicit_context extension
    if registry_xml.support_EGL_ANGLE_explicit_context:
        comment = "\n// EGL_ANGLE_explicit_context"
        extension_defs.append(comment)
        extension_decls.append(comment)
        libgles_ep_defs.append(comment)

        cmds = xml.all_cmd_names.get_all_commands()

        # Get the explicit context entry points
        decls, defs, libgles_defs, validation_protos = get_entry_points(
            xml.all_commands, cmds, True)

        # Append the explicit context entry points
        extension_decls += decls
        extension_defs += defs
        libgles_ep_defs += libgles_defs

        libgles_ep_exports.append("\n    ; EGL_ANGLE_explicit_context")
        libgles_ep_exports += get_exports(cmds, lambda x: "%sContextANGLE" % x)

        # Generate .inc files for extension function pointers and declarations
        for major, minor in [[2, 0], [3, 0], [3, 1], [1, 0]]:
            annotation = "{}_{}".format(major, minor)

            major_if_not_one = major if major != 1 else ""
            minor_if_not_zero = minor if minor != 0 else ""
            version = "{}{}".format(major_if_not_one, minor_if_not_zero)

            glext_ptrs, glext_protos = get_glext_decls(all_commands,
                xml.all_cmd_names.get_commands(annotation), version, True)

            glext_ext_ptrs = []
            glext_ext_protos = []

            # Append extensions for 1.0 and 2.0
            if(annotation == "1_0"):
                glext_ext_ptrs, glext_ext_protos = get_glext_decls(all_commands,
                    xml.all_cmd_names.get_commands("glext"), version, True)
            elif(annotation == "2_0"):
                glext_ext_ptrs, glext_ext_protos = get_glext_decls(all_commands,
                    xml.all_cmd_names.get_commands("gl2ext"), version, True)

            glext_ptrs += glext_ext_ptrs
            glext_protos += glext_ext_protos

            write_glext_explicit_context_inc(version, "\n".join(glext_ptrs), "\n".join(glext_protos))


    header_includes = template_header_includes.format(
        major="", minor="")
    header_includes += """
    #include <GLES/glext.h>
    #include <GLES2/gl2.h>
    #include <GLES2/gl2ext.h>
    """

    source_includes = template_sources_includes.format("ext", "EXT", "")
    source_includes += """
    #include "libANGLE/validationES1.h"
    #include "libANGLE/validationES2.h"
    #include "libANGLE/validationES3.h"
    #include "libANGLE/validationES31.h"
    """

    write_file("ext", "extension", template_entry_point_header,
               "\n".join([item for item in extension_decls]), "h", header_includes,
               "gl.xml and gl_angle_ext.xml")
    write_file("ext", "extension", template_entry_point_source,
               "\n".join([item for item in extension_defs]), "cpp", source_includes,
               "gl.xml and gl_angle_ext.xml")

    write_validation_header("EXT", "extension", ext_validation_protos)

    write_context_api_decls("1_0", context_gles_header, gles1decls)

    sorted_cmd_names = ["Invalid"] + [cmd[2:] for cmd in sorted(xml.all_cmd_names.get_all_commands())]

    entry_points_enum = template_entry_points_enum_header.format(
        script_name = os.path.basename(sys.argv[0]),
        data_source_name = "gl.xml and gl_angle_ext.xml",
        year = date.today().year,
        entry_points_list = ",\n".join(["    " + cmd for cmd in sorted_cmd_names]))

    entry_points_enum_header_path = path_to("libGLESv2", "entry_points_enum_autogen.h")
    with open(entry_points_enum_header_path, "w") as out:
        out.write(entry_points_enum)
        out.close()

    source_includes = """
    #include "angle_gl.h"

    #include "libGLESv2/entry_points_gles_1_0_autogen.h"
    #include "libGLESv2/entry_points_gles_2_0_autogen.h"
    #include "libGLESv2/entry_points_gles_3_0_autogen.h"
    #include "libGLESv2/entry_points_gles_3_1_autogen.h"
    #include "libGLESv2/entry_points_gles_ext_autogen.h"

    #include "common/event_tracer.h"
    """

    write_export_files("\n".join([item for item in libgles_ep_defs]), source_includes)

    libgles_ep_exports += get_egl_exports()

    everything = "Khronos and ANGLE XML files"
    write_windows_def_file(everything, "libGLESv2", libgles_ep_exports)

if __name__ == '__main__':
    sys.exit(main())
