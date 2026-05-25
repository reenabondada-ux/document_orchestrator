# Document Orchestrator API

## Create a run
`POST /documents`

## List runs
`GET /documents`

## Get a run
`GET /documents/{run_id}`

## List sections
`GET /documents/{run_id}/sections`

## Get a section
`GET /documents/{run_id}/sections/{section_name}`

## Generate a section
`POST /documents/{run_id}/generate`

## Approve a section
`POST /documents/{run_id}/sections/{section_name}/approve`

## Regenerate a section
`POST /documents/{run_id}/sections/{section_name}/regenerate`

## List retrieval passes
`GET /documents/{run_id}/retrieval-passes`

## View lifecycle events
`GET /documents/{run_id}/events`

## Export the document
`POST /documents/{run_id}/export`
