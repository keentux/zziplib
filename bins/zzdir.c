/*
 *	Copyright (c) 2000,2001,2002 Guido Draheim <guidod@gmx.de>
 *      Use freely under the restrictions of the ZLIB license.
 */

#include <zzip/zzip.h>
#include <stdio.h>
#include <string.h>

#ifndef EX_NOINPUT
#define EX_NOINPUT 66
#endif

#ifndef EX_IOERR
#define EX_IOERR 74
#endif

static const char usage[] = /* .. */
    {"zzdir <dir>.. \n"
     "  - prints a content table to stdout, but the dir can also be a zip-arch."
     "\n"
     " To show the contents of a zip-archive named 'test.zip', you may write \n"
     "     zzdir test \n"};

#define BASENAME(x) (strchr((x), '/') ? strrchr((x), '/') + 1 : (x))

static int
unzzip_version(void)
{
    printf("%s version %s %s\n", BASENAME(__FILE__), ZZIP_PACKAGE_NAME, ZZIP_PACKAGE_VERSION);
    return 0;
}

static int
unzzip_help(void)
{
    printf(usage);
    return 0;
}

int
main(int argc, char** argv)
{
    int argn;
    int exitcode = 0;

    if (argc <= 1 || ! strcmp(argv[1], "--help")) {
        return unzzip_help();
    }
    if (! strcmp(argv[1], "--version")) {
        return unzzip_version();
    }

    for (argn = 1; argn < argc; argn++) {
        ZZIP_DIR*    dir;
        ZZIP_DIRENT* d;

        dir = zzip_opendir(argv[argn]);
        if (! dir) {
            fprintf(stderr, "did not open %s: ", argv[argn]);
            perror(argv[argn]);
            exitcode = EX_NOINPUT;
            continue;
        }

        if (argc > 2)
            printf("%s: \n", argv[argn]);

        /* read each dir entry and show one line of info per file */
        while ((d = zzip_readdir(dir))) {
            /* orignalsize / compression-type / compression-ratio / filename */
            if (d->st_size > 999999) {
                printf("%5dK %-9s %2d%% %s\n",                            /* .. */
                       d->st_size >> 10,                                  /* .. */
                       zzip_compr_str(d->d_compr),                        /* .. */
                       100 - (d->d_csize | 1) / ((d->st_size / 100) | 1), /* .. */
                       d->d_name);
            }
            else {
                printf("%6d %-9s %2d%% %s\n",                           /* .. */
                       d->st_size,                                      /* .. */
                       zzip_compr_str(d->d_compr),                      /* .. */
                       100 - (d->d_csize | 1) * 100 / (d->st_size | 1), /* .. */
                       d->d_name);
            }
        }

        zzip_closedir(dir);
    }

    return exitcode;
}
