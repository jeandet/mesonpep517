if run_command(python, '-c', 'import hotdoc').returncode() != 0
    message('Not building documentation')
    subdir_done()
endif

hotdoc = import('hotdoc')
libs_doc = [hotdoc.generate_doc('mesonpep517',
    project_version: meson.project_version(),
    sitemap: 'sitemap.txt',
    index: 'index.md',
)]