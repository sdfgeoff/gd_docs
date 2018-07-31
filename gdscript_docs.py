"""
A minimal documentation generator.

Looks for:
# PUBLIc
#
# docs
# more docs
# more docs
thing
    '''yet more docs
    and some more again'''

Documentation is expected to be in markdown format. Paths starting with res://
are resolved into links


"""

import argparse
import configparser
import sys
import os
import traceback


IGNORES = ["modules"]
PUBLIC_TAG = "# PUBLIC"

def clean_path(path, project_dir=''):
    return os.path.join(project_dir, path.replace('res://', ''))


def get_autoloads(project_dir, project_file):
    raw = get_between(open(project_file).read(), '[autoload]', '[', multiline=True)[1]
    autoloads = {}
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        cleaned = line.split('="*')
        autoloads[cleaned[0]] = clean_path(cleaned[1][:-1], project_dir)
    return autoloads


def ensure_dir(directory):
    """Ensures a directory exists, recursively making it if necessary"""
    if not directory:
        return
    parent_dirs = directory.split(os.sep)
    for id, par_dir in enumerate(parent_dirs):
        parent_dir = os.sep.join(parent_dirs[:id])
        if parent_dir and not os.path.exists(parent_dir):
            os.mkdir(parent_dir)

    if not os.path.exists(directory):
        os.mkdir(directory)



def generate_index(autoloads, class_list, outfolder, projectdir):
    outfile = open(os.path.join(outfolder, 'index.md'), 'w')
    outfile.write("# Generated Documentation Index\n")
    outfile.write("## Autoloads\n")
    for autoload in autoloads:
        outfile.write("- [{}]({})\n".format(
            autoload,
            localise_path(outfolder, projectdir, autoloads[autoload])
        ))

    outfile.write("\n## Classes\n")

    for class_path in class_list:
        outfile.write("- [{}]({})\n".format(
            os.path.basename(class_path)[:-3],
            localise_path(outfolder, projectdir, class_path)
        ))


def find_script(tscn_file, projectdir):
    """Returns the script associated with a tscn file"""
    data = open(tscn_file).read()
    # Root node is always first
    root_node = get_between(data, "[node ", "[", multiline=True)
    if root_node != None:
        resource = get_between(root_node[1], "script = ExtResource(", ")")
        if resource != None:
            resource_id = int(resource[1])
            path = get_between(
                data,
                "[ext_resource path=\"",
                '" type="Script" id={}'.format(resource_id)
            )
            if path is not None:
                return clean_path(path[1], projectdir)
    return tscn_file.replace(".tscn", ".gd")  # We hope




def localise_path(outfolder, projectdir, script):
    """Taking two files in the godot project directory, generates the name
    of the file the documentation should be stored in"""
    if script.endswith(".tscn"):
        script = find_script(script, projectdir)
    path = os.path.relpath(script, projectdir)
    path = path.replace('.gd', '.md')
    return os.path.join(outfolder, path)


def generate_script_doc(project_path, script_file, outfolder):
    script_data = open(script_file).read()
    has_public = False

    all_things = {}

    start = script_data.find(PUBLIC_TAG)
    while start != -1:
        has_public = True
        data = script_data[start+len(PUBLIC_TAG)+1:]

        docs = ""
        things = ""

        has_docstr = False
        for line in data.split('\n'):
            if line.startswith('#'):
                docs += line[1:].strip()  + '\n'

            elif line.find('"""') != -1:
                if has_docstr or line.count('"""') == 2:
                    line = line.replace('"""', '')
                    docs += line.strip() + '\n'
                    break
                else:
                    has_docstr = True
                line = line.replace('"""', '')
                docs += line.strip() + '\n'

            elif line.find("'''") != -1:

                if has_docstr or line.count("'''") == 2:
                    line = line.replace("'''", '')
                    docs += line.strip() + '\n'
                else:
                    has_docstr = True
                line = line.replace("'''", '')
                docs += line.strip() + '\n'


            else:
                if has_docstr:
                    docs += line.strip() + '\n'
                elif line:
                    things += line
                else:
                    break


        all_things[things] = docs

        start = script_data.find("# PUBLIC", start+1)


    if has_public:
        outpath = localise_path(outfolder, project_path, script_file)
        ensure_dir(os.path.dirname(outpath))

        outfile = open(outpath, 'w')
        outfile.write("# {}\n\n".format(os.path.relpath(script_file, project_path)))

        for thing in all_things:
            outfile.write("### {}\n\n".format(markup_docs(
                thing,
                project_path,
                outfolder,
                outpath
            )))
            outfile.write("{}\n\n".format(markup_docs(
                all_things[thing],
                project_path,
                outfolder,
                outpath
            )))


        return True
    return False



def markup_docs(docs, project_dir, outfolder, ownpath):
    """eg converts paths starting with res:// into urls"""

    def format_url(url):
        full = "res://" + found[1]
        relpath = os.path.relpath(
            localise_path(outfolder, project_dir, clean_path(full, project_dir)),
            os.path.dirname(ownpath),
        )

        return docs.replace(full, "[{}]({})".format(
            os.path.basename(url),
            relpath,
        ))

    # And this is why I should learn regex
    found = get_between(docs, "res://", " ")
    if found != None:
        docs = format_url(found[1])
        found = get_between(docs, "res://", " ")
    found = get_between(docs, "res://", "\n")
    if found != None:
        docs = format_url(found[1])
        found = get_between(docs, "res://", "\n")
    found = get_between(docs, "res://", '"')
    if found != None:
        docs = format_url(found[1])
        found = get_between(docs, "res://", '"')


    return docs


def main(args):
    parser = argparse.ArgumentParser('Look for spare .import files')
    parser.add_argument('--projectfile', required=True, help='The godot.project file')
    parser.add_argument('--outfolder', required=True, help='Folder to output to')
    args = parser.parse_args(args)

    projectdir = os.path.dirname(os.path.abspath(args.projectfile))
    ensure_dir(args.outfolder)
    args.outfolder = os.path.abspath(args.outfolder)

    script_files = []
    for folder, subfolders, files in os.walk(projectdir):
        for filename in files:
            full_path = os.path.join(folder, filename)
            ignored = True

            if filename.endswith('.gd'):
                ignored = False

            for ignore in IGNORES:
                if ignore in full_path:
                    ignored = True

            if not ignored:
                script_files.append(full_path)

    public_scripts = []
    for class_path in script_files:
        if generate_script_doc(projectdir, class_path, args.outfolder):
            public_scripts.append(class_path)

    generate_index(
        get_autoloads(projectdir, args.projectfile),
        public_scripts,
        args.outfolder,
        projectdir
    )


def get_between(string, start_str, end_str, pos=0, multiline=False):
    found = []
    start_index = string.find(start_str, pos)
    if start_index == -1:
        return
    end_index = string.find(end_str, max(start_index+len(start_str), pos))
    if end_index == -1:
        return
    res = string[start_index + len(start_str):end_index]
    if '\n' in res and not multiline:
        pass
    else:
        return (start_index, end_index), res


if __name__ == "__main__":
    main(sys.argv[1:])
