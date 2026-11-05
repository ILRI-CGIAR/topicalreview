#!/usr/bin/env Rscript
# Offline JSONL -> dashboard tables. No database, API or GitHub access.
args <- commandArgs(trailingOnly = TRUE)
arg <- function(name, default = NULL) {
  i <- match(name, args)
  if (is.na(i) || i == length(args)) default else args[[i + 1L]]
}
input <- arg('--input'); out <- arg('--out', 'local_output')
if (is.null(input) || !file.exists(input)) stop('Use --input with an existing JSONL file')
if (!requireNamespace('jsonlite', quietly = TRUE)) stop('Install jsonlite')
lines <- readLines(input, warn = FALSE, encoding = 'UTF-8')
lines <- lines[nzchar(trimws(lines))]
if (!length(lines)) stop('Empty JSONL input')
records <- lapply(seq_along(lines), function(i) tryCatch(
  jsonlite::fromJSON(lines[[i]], simplifyVector = FALSE),
  error = function(e) stop(sprintf('Line %d: %s', i, conditionMessage(e)))))
required <- c('schema_version','article_id','file_name','bibliographic',
 'bibliographic_provenance','geography','thematic_codes','climate_hazards',
 'entities','adaptation','mitigation','methods','extraction_provenance')
scalar <- function(x) if (is.null(x) || length(x) == 0L) '' else as.character(x[[1]])
validate_list <- function(x, where) if (!is.list(x)) stop(where, ' must be an array/object')
check_node <- function(node, where) {
  if (is.null(node) || !is.list(node) || !is.character(node$code) ||
      length(node$code) != 1L || !nzchar(trimws(node$code)) ||
      !is.character(node$label) || length(node$label) != 1L ||
      !nzchar(trimws(node$label))) stop(where, ' requires nonempty code and label')
}
make_row <- function(...) unlist(list(...), use.names = TRUE)
a <- list(); ctry <- list(); theme <- list(); facet <- list(); flags <- list()
add <- function(x, row) { x[[length(x)+1L]] <- row; x }
seen <- character()
for (r in records) {
  if (!is.list(r) || !all(required %in% names(r)))
    stop('Missing top-level fields: ', paste(setdiff(required,names(r)), collapse=', '))
  id <- r$article_id
  if (!identical(r$schema_version,'1.1') || !is.character(id) || length(id)!=1L || !nzchar(id))
    stop('Invalid schema_version or article_id')
  if (id %in% seen) stop('Duplicate article_id: ', id)
  seen <- c(seen,id)
  b <- r$bibliographic
  if (!is.list(b) || !all(c('authors','year_published','title','source','volume','issue','pages','doi','abstract','external_ids') %in% names(b)))
    stop(id, ': incomplete bibliographic block')
  if (!is.null(b$year_published) && !(is.numeric(b$year_published) && length(b$year_published)==1L))
    stop(id, ': year_published must be a number or null')
  if (!is.list(b$authors) || !is.list(b$external_ids)) stop(id, ': authors and external_ids must be arrays')
  for (ext in b$external_ids) if (!is.list(ext) || !is.character(ext$type) || !nzchar(scalar(ext$type)) || !is.character(ext$value) || !nzchar(scalar(ext$value))) stop(id, ': invalid external ID')
  a <- add(a, make_row(article_id=id, file_name=scalar(r$file_name), title=scalar(b$title),
    year_published=scalar(b$year_published), source=scalar(b$source$title), doi=scalar(b$doi),
    review_status=scalar(r$extraction_provenance$review_status)))
  geo <- r$geography
  if (!is.list(geo) || !is.list(geo$countries_iso3)) stop(id, ': countries_iso3 must be an array')
  for (cc in geo$countries_iso3) {
    if (!is.character(cc) || length(cc)!=1L || !grepl('^[A-Z]{3}$', cc)) stop(id, ': invalid ISO3 syntax')
    ctry <- add(ctry, make_row(article_id=id, iso3=cc))
  }
  if (!is.list(r$thematic_codes)) stop(id, ': thematic_codes must be array')
  for (assignment in r$thematic_codes) {
    check_node(assignment$level_1, paste(id,'level_1'))
    if (!is.null(assignment$level_2)) {
      check_node(assignment$level_2, paste(id,'level_2'))
      if (!startsWith(assignment$level_2$code, paste0(assignment$level_1$code,'.')))
        stop(id, ': Level 2 code does not match Level 1 prefix')
    }
    if (!is.null(assignment$level_3)) {
      if (is.null(assignment$level_2)) stop(id, ': Level 3 without Level 2')
      check_node(assignment$level_3, paste(id,'level_3'))
      if (!startsWith(assignment$level_3$code, paste0(assignment$level_2$code,'.')))
        stop(id, ': Level 3 code does not match Level 2 prefix')
    }
    theme <- add(theme, make_row(article_id=id,
      level_1_code=assignment$level_1$code, level_1_label=assignment$level_1$label,
      level_2_code=if(is.null(assignment$level_2)) '' else assignment$level_2$code,
      level_2_label=if(is.null(assignment$level_2)) '' else assignment$level_2$label,
      level_3_code=if(is.null(assignment$level_3)) '' else assignment$level_3$code,
      level_3_label=if(is.null(assignment$level_3)) '' else assignment$level_3$label))
  }
  for (field in c('climate_hazards')) for (v in r[[field]]) facet <- add(facet, make_row(article_id=id,variable=field,value=v))
  for (obj in c('entities','adaptation','mitigation','methods')) {
    for (nm in names(r[[obj]])) {
      v <- r[[obj]][[nm]]
      if (is.logical(v) || is.null(v)) {
        if (!is.null(v) && length(v)!=1L) stop(id, ': invalid boolean ', obj,'.',nm)
        flags <- add(flags, make_row(article_id=id,variable=paste(obj,nm,sep='.'),value=if(is.null(v)) '' else tolower(as.character(v))))
      } else {
        if (!is.list(v)) stop(id, ': expected array for ',obj,'.',nm)
        for (item in v) {
          if (!is.character(item) || length(item)!=1L) stop(id, ': invalid facet ',obj,'.',nm)
          facet <- add(facet, make_row(article_id=id,variable=paste(obj,nm,sep='.'),value=item))
        }
      }
    }
  }
}
output <- list(articles=a,article_countries=ctry,article_thematic_codes=theme,article_facets=facet,article_flags=flags)
headers <- list(articles=c('article_id','file_name','title','year_published','source','doi','review_status'),
 article_countries=c('article_id','iso3'),
 article_thematic_codes=c('article_id','level_1_code','level_1_label','level_2_code','level_2_label','level_3_code','level_3_label'),
 article_facets=c('article_id','variable','value'), article_flags=c('article_id','variable','value'))
# Write into an entirely new output location to prevent stale results being mistaken for current results.
if (dir.exists(out) && length(list.files(out,all.files=TRUE,no..=TRUE))) stop('Output directory must be empty: ',out)
dir.create(out, recursive=TRUE, showWarnings=FALSE)
for (name in names(output)) {
  h <- headers[[name]]
  d <- if (!length(output[[name]])) as.data.frame(setNames(replicate(length(h),character(),simplify=FALSE),h)) else {
    d <- as.data.frame(do.call(rbind,output[[name]]),stringsAsFactors=FALSE); d[,h,drop=FALSE]
  }
  utils::write.csv(d,file.path(out,paste0(name,'.csv')),row.names=FALSE,na='')
}
file.copy(input,file.path(out,'canonical.jsonl'),overwrite=FALSE)
cat('Validated',length(records),'records; wrote dashboard tables to',out,'\n')
