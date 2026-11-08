#!/usr/bin/env Rscript
# Source-first preflight for CGIAR topicalreview. This does NOT infer ontology codes.
# Rscript R/legacy_preflight.R --input /path/A_FileFor_BerenguerJose1.xlsx --out /path/empty_output
args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(key, default = NULL) {
  i <- match(key, args)
  if (is.na(i) || i == length(args)) default else args[[i + 1L]]
}
input <- get_arg('--input'); out <- get_arg('--out', 'local_audit')
if (is.null(input) || !file.exists(input)) stop('Use --input with the local workbook')
if (!requireNamespace('readxl', quietly=TRUE) ||
    !requireNamespace('jsonlite', quietly=TRUE)) stop('Install readxl and jsonlite')
if (dir.exists(out) && length(list.files(out, all.files=TRUE, no..=TRUE)))
  stop('Output directory must be empty: ', out)
d <- readxl::read_excel(input, sheet='data', col_types='text', .name_repair='minimal')
required <- c('Filenames','Title','DOI','Citation','Included Articles','Published year',
              '3. Adaptation options in agrifood system ', '3.5 Climate Information System',
              '5.2 Method time scale')
if (!all(required %in% names(d)) || anyDuplicated(names(d)))
  stop('Source headers do not match the audited worksheet; review before continuing')
cell <- function(i, col) {
  x <- d[[col]][i]
  if (is.na(x)) '' else trimws(x)
}
rows <- list()
add <- function(i, col, issue, value) {
  rows[[length(rows)+1L]] <<- data.frame(
    excel_row=i+1L, column=col, issue=issue, source_value=value,
    stringsAsFactors=FALSE)
}
groups <- list(
  c('Impact of climate change on agrifood systems',
    '1. Impacts of climate change on agrifood systems','1.1 Natural System',
    '1.2 Agricultural System','1.3 Human System'),
  c('Impact of agrifood systems on climate change',
    '2. Impacts of agrifood systems on climate change',
    '2.1 Deforestation and Land Use Change','2.2 Agricultural Practices ',
    '2.3 Energy Use/ Post production/Food loss and waste'),
  c('Adaptation options in agrifood system',
    '3. Adaptation options in agrifood system ',
    '3.1 Crops/livestock/fishery/land related adaptation',
    '3.2 Water related adaptation',
    '3.3 Society/livelihood/economy related adaptation ',
    '3.4 Health/urban related adaptations.','3.5 Climate Information System'),
  c('Mitigation options in agrifood system',
    '4. Mitigation options in agrifood system ',
    '4.1 Mitigation of N2O from fertilizers/soil/manure',
    '4.2 Mitigation of methane from rice/livestock/food loss and waste',
    '4.3 Mitigation of CO2/GHG from agriculture/forest'))
if (!all(unlist(groups) %in% names(d))) stop('Unexpected thematic column names')
for (i in seq_len(nrow(d))) {
  for (group in groups) {
    flag <- tolower(cell(i, group[[1]]))
    vals <- vapply(group[-1], function(nm) cell(i,nm),character(1))
    coded <- nzchar(vals) & !grepl('not relevant', vals, ignore.case=TRUE)
    if (flag == 'false' && any(coded))
      add(i,group[[1]],'FALSE_WITH_THEMATIC_CODING',paste(group[-1][coded], collapse='; '))
  }
  if (grepl('other',cell(i,'3. Adaptation options in agrifood system '),ignore.case=TRUE))
    add(i,'3. Adaptation options in agrifood system ','UNAPPROVED_OTHER_HIERARCHY',
        cell(i,'3. Adaptation options in agrifood system '))
  v <- cell(i,'3.5 Climate Information System')
  if (nzchar(v) && v != 'CIEW')
    add(i,'3.5 Climate Information System','UNEXPECTED_CLIMATE_INFORMATION_VALUE',v)
}
# Audit option numbers within each column, never assuming an option number has one meaning.
for (col in c('5.2 Method time scale')) {
  seen <- list()
  for (i in seq_len(nrow(d))) {
    for (option in strsplit(cell(i,col),'|||',fixed=TRUE)[[1]]) {
      m <- regexec('^\\s*([0-9]+)\\.\\s*(.*)$',trimws(option))
      fields <- regmatches(trimws(option),m)[[1]]
      if (length(fields) == 3L)
        seen[[fields[[2]]]] <- unique(c(seen[[fields[[2]]]],trimws(fields[[3]])))
    }
  }
  for (num in names(seen)) if (length(seen[[num]]) > 1L)
    add(1L,col,'OPTION_NUMBER_CONFLICT',paste0(num,': ',paste(seen[[num]],collapse=' | ')))
}
dir.create(out,recursive=TRUE,showWarnings=FALSE)
audit <- if (length(rows)) do.call(rbind,rows) else data.frame(
 excel_row=integer(),column=character(),issue=character(),source_value=character())
write.csv(audit,file.path(out,'review_flags.csv'),row.names=FALSE,na='')
con <- file(file.path(out,'legacy_source_rows.jsonl'),open='wt',encoding='UTF-8')
for (i in seq_len(nrow(d))) {
  v <- lapply(as.list(d[i,,drop=FALSE]),function(x) if (is.na(x)) NULL else as.character(x))
  writeLines(jsonlite::toJSON(list(excel_row=i+1L, source_data=v),
                             auto_unbox=TRUE,null='null'),con)
}
close(con)
cat('Audited ',nrow(d),' rows; ',nrow(audit),' flags. No canonical JSONL generated.\\n',sep='')
cat('Resolve conflicting labels and approve an exact source-value -> code AND label crosswalk first.\\n')
