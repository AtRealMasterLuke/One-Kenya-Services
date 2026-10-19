# ZAP Scanning Report

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 0 |
| Low | 1 |
| Informational | 5 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Info | Informational | http://web-prod:8000 | Percentage of responses with status code 2xx | 66 % |
| Info | Informational | http://web-prod:8000 | Percentage of responses with status code 4xx | 33 % |
| Info | Informational | http://web-prod:8000 | Percentage of endpoints with content type text/css | 12 % |
| Info | Informational | http://web-prod:8000 | Percentage of endpoints with content type text/html | 87 % |
| Info | Informational | http://web-prod:8000 | Percentage of endpoints with method GET | 75 % |
| Info | Informational | http://web-prod:8000 | Percentage of endpoints with method POST | 25 % |
| Info | Informational | http://web-prod:8000 | Count of total endpoints | 8    |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| Cross-Origin-Embedder-Policy Header Missing or Invalid | Low | 4 |
| Authentication Request Identified | Informational | 1 |
| Non-Storable Content | Informational | 2 |
| Session Management Response Identified | Informational | 4 |
| Storable and Cacheable Content | Informational | Systemic |
| User Controllable HTML Element Attribute (Potential XSS) | Informational | 4 |




## Alert Detail



### [ Cross-Origin-Embedder-Policy Header Missing or Invalid ](https://www.zaproxy.org/docs/alerts/90004/)



##### Low (Medium)

### Description

Cross-Origin-Embedder-Policy header is a response header that prevents a document from loading any cross-origin resources that don't explicitly grant the document permission (using CORP or CORS).

* URL: http://web-prod:8000/
  * Node Name: `http://web-prod:8000/`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://web-prod:8000/accounts/login/
  * Node Name: `http://web-prod:8000/accounts/login/`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``


Instances: 4

### Solution

Ensure that the application/web server sets the Cross-Origin-Embedder-Policy header appropriately, and that it sets the Cross-Origin-Embedder-Policy header to 'require-corp' for documents.
If possible, ensure that the end user uses a standards-compliant and modern web browser that supports the Cross-Origin-Embedder-Policy header (https://caniuse.com/mdn-http_headers_cross-origin-embedder-policy).

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 14

#### Source ID: 3

### [ Authentication Request Identified ](https://www.zaproxy.org/docs/alerts/10111/)



##### Informational (High)

### Description

The given request has been identified as an authentication request. The 'Other Info' field contains a set of key=value lines which identify any relevant fields. If the request is in a context which has an Authentication Method set to "Auto-Detect" then this rule will change the authentication to match the request identified.

* URL: http://web-prod:8000/accounts/login/
  * Node Name: `http://web-prod:8000/accounts/login/ ()(csrfmiddlewaretoken,next,password,username)`
  * Method: `POST`
  * Parameter: `username`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=username
userValue=ZAP
passwordParam=password
referer=http://web-prod:8000/accounts/login/
csrfToken=csrfmiddlewaretoken`


Instances: 1

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/)



#### Source ID: 3

### [ Non-Storable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are not storable by caching components such as proxy servers. If the response does not contain sensitive, personal or user-specific information, it may benefit from being stored and cached, to improve performance.

* URL: http://web-prod:8000/accounts/login/
  * Node Name: `http://web-prod:8000/accounts/login/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``
* URL: http://web-prod:8000/accounts/login/
  * Node Name: `http://web-prod:8000/accounts/login/ ()(csrfmiddlewaretoken,next,password,username)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``


Instances: 2

### Solution

The content may be marked as storable by ensuring that the following conditions are satisfied:
The request method must be understood by the cache and defined as being cacheable ("GET", "HEAD", and "POST" are currently defined as cacheable)
The response status code must be understood by the cache (one of the 1XX, 2XX, 3XX, 4XX, or 5XX response classes are generally understood)
The "no-store" cache directive must not appear in the request or response header fields
For caching by "shared" caches such as "proxy" caches, the "private" response directive must not appear in the response
For caching by "shared" caches such as "proxy" caches, the "Authorization" header field must not appear in the request, unless the response explicitly allows it (using one of the "must-revalidate", "public", or "s-maxage" Cache-Control response directives)
In addition to the conditions above, at least one of the following conditions must also be satisfied by the response:
It must contain an "Expires" header field
It must contain a "max-age" response directive
For "shared" caches such as "proxy" caches, it must contain a "s-maxage" response directive
It must contain a "Cache Control Extension" that allows it to be cached
It must have a status code that is defined as cacheable by default (200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501).

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3

### [ Session Management Response Identified ](https://www.zaproxy.org/docs/alerts/10112/)



##### Informational (Medium)

### Description

The given response has been identified as containing a session management token. The 'Other Info' field contains a set of header tokens that can be used in the Header Based Session Management Method. If the request is in a context which has a Session Management Method set to "Auto-Detect" then this rule will change the session management to use the tokens identified.

* URL: http://web-prod:8000/accounts/login/
  * Node Name: `http://web-prod:8000/accounts/login/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`


Instances: 4

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/)



#### Source ID: 3

### [ Storable and Cacheable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are storable by caching components such as proxy servers, and may be retrieved directly from the cache, rather than from the origin server by the caching servers, in response to similar requests from other users. If the response data is sensitive, personal or user-specific, this may result in sensitive information being leaked. In some cases, this may even result in a user gaining complete control of the session of another user, depending on the configuration of the caching components in use in their environment. This is primarily an issue where "shared" caching servers such as "proxy" caches are configured on the local network. This configuration is typically found in corporate or educational environments, for instance.

* URL: http://web-prod:8000/
  * Node Name: `http://web-prod:8000/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://web-prod:8000/robots.txt
  * Node Name: `http://web-prod:8000/robots.txt`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://web-prod:8000/sitemap.xml
  * Node Name: `http://web-prod:8000/sitemap.xml`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://web-prod:8000/static/css/site.13d4e869ee7c.css
  * Node Name: `http://web-prod:8000/static/css/site.13d4e869ee7c.css`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `max-age=315360000`
  * Other Info: ``

Instances: Systemic


### Solution

Validate that the response does not contain sensitive, personal or user-specific information. If it does, consider the use of the following HTTP response headers, to limit, or prevent the content being stored and retrieved from the cache by another user:
Cache-Control: no-cache, no-store, must-revalidate, private
Pragma: no-cache
Expires: 0
This configuration directs both HTTP 1.0 and HTTP 1.1 compliant caching servers to not store the response, and to not retrieve the response (without validation) from the cache, in response to a similar request.

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3

### [ User Controllable HTML Element Attribute (Potential XSS) ](https://www.zaproxy.org/docs/alerts/10031/)



##### Informational (Low)

### Description

This check looks at user-supplied input in query string parameters and POST data to identify where certain HTML attribute values might be controlled. This provides hot-spot detection for XSS (cross-site scripting) that will require further review by a security analyst to determine exploitability.

* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `full_name`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://web-prod:8000/accounts/register/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
full_name=ZAP

The user-controlled value was:
zap`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `password1`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://web-prod:8000/accounts/register/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
password1=ZAP

The user-controlled value was:
zap`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `password2`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://web-prod:8000/accounts/register/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
password2=ZAP

The user-controlled value was:
zap`
* URL: http://web-prod:8000/accounts/register/
  * Node Name: `http://web-prod:8000/accounts/register/ ()(csrfmiddlewaretoken,full_name,password1,password2,phone)`
  * Method: `POST`
  * Parameter: `phone`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://web-prod:8000/accounts/register/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
phone=9999999999

The user-controlled value was:
9999999999`


Instances: 4

### Solution

Validate all input and sanitize output it before writing to any HTML attributes.

### Reference


* [ https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)


#### CWE Id: [ 20 ](https://cwe.mitre.org/data/definitions/20.html)


#### WASC Id: 20

#### Source ID: 3


