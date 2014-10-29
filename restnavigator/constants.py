import httplib

GET = 'get'
POST = 'post'
DELETE = 'delete'

POSITIVE_STATUS_CODES  = {
    DELETE: (httplib.ACCEPTED,httplib.NO_CONTENT,httplib.SEE_OTHER,httplib.OK ),
    POST: (httplib.CREATED, httplib.ACCEPTED,httplib.FOUND,httplib.SEE_OTHER,httplib.OK)}