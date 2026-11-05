# Run from repository root: Rscript tests/smoke_test.R
out <- tempfile('cgiar-test-')
status <- system2('Rscript', c('R/build_tables.R','--input','examples/example.jsonl','--out',out))
stopifnot(status == 0L, file.exists(file.path(out,'article_thematic_codes.csv')))
d <- read.csv(file.path(out,'article_thematic_codes.csv'))
stopifnot(nrow(d)==1L, d$level_1_code[[1]]=='3', d$level_1_label[[1]]=='Adaptation options in agri-food systems')
unlink(out,recursive=TRUE)
cat('Smoke test passed\n')
