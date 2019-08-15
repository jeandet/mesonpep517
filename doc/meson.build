if run_command(python, '-c', 'import hotdoc').returncode() != 0
    message('Not building documentation')
    subdir_done()
endif

if not find_program('hotdoc', required: false).found()
    message('Not building documentation')
    subdir_done()
endif

res = run_command(find_program('generate_doc.py'), 'pyproject.md.in', 'pyproject.md')
if res.returncode() != 0
    error('Could not update doc: @0@ - @1@'.format(res.stderr(), res.stdout()))
endif

hotdoc = import('hotdoc')
libs_doc = [hotdoc.generate_doc('mesonpep517',
    project_version: meson.project_version(),
    sitemap: 'sitemap.txt',
    index: 'index.md',
)]