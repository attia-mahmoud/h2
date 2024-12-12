def verifyregex(frame, attribute, regex):
    return frame[attribute].matches(regex)

def verifylength(event, length):
    result = len(event.data) == length
    if result:
        return f"Frame length is equal to {length}"
    else:
        return f"Frame length is not equal to {length}"
    
def verifystreamid(event, stream_id):
    result = event.stream_id == int(stream_id)
    if result:
        return f"Stream ID is equal to {stream_id}"
    else:
        return f"Stream ID is not equal to {stream_id}"

function_map = {
    'verifyregex': verifyregex,
    'verifylength': verifylength,
    'verifystreamid': verifystreamid
}