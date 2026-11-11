def parts: .result.history[]?.parts[]?;
def calls: [parts | select(.metadata.kagent_type == "function_call") | .data];
def responses: [parts | select(.metadata.kagent_type == "function_response") | .data
  | select((.id | type) == "string" and (.id | length) > 0 and (.response | type) == "object")];
. as $body | calls as $calls | responses as $responses
| if .error or .result.status.state != "completed" then error("Native task is not completed") else . end
| if ($expected | length) != 1 or ($expected[0] | type) != "array" or ($expected[0] | length) == 0
  then error("Supply a nonempty expected call contract with --slurpfile expected") else . end
| [$expected[0][] as $want
   | [$calls[] | select(.name == $want.name and .args == $want.args)] as $matches
   | {label: $want.label, name: $want.name, exactMatchCount: ($matches | length),
      results: [$matches[] as $call
        | [$responses[] | select(.id == $call.id and .name == $call.name)] as $returned
        | {callId: $call.id, returned: (($returned | length) == 1),
           explicitError: any($returned[]; .response.isError == true or
             (.response.error != null and .response.error != false))}]}] as $observations
| {taskId: $body.result.id, state: $body.result.status.state,
   nativeHistoryAvailable: (($calls | length) > 0), expectedCalls: $observations,
   allCallIdsValid: (all($calls[]; (.id | type) == "string" and (.id | length) > 0)
     and ([$calls[].id] | length) == ([$calls[].id] | unique | length)),
   unexpectedCalls: [$calls[] as $call
     | select(any($expected[0][]; .name == $call.name and .args == $call.args) | not)
     | {name:$call.name,callId:$call.id}],
   allExpectedCallsReturned: all($observations[];
     .exactMatchCount == 1 and (.results | length) == 1 and .results[0].returned and (.results[0].explicitError | not)),
   scope: "Native call and returned-result evidence. Backend completion and authorization need separate evidence."}
| if .allExpectedCallsReturned and .allCallIdsValid and (.unexpectedCalls | length) == 0
  then . else ., error("Missing, ambiguous, unexpected or explicitly failed native tool result. Do not infer from answer text.") end
