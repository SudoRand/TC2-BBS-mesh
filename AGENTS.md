# Tips for AI coding agents:

## Checking the second to last message of output

It is tempting to try to perform unit testing assertions on the last message of output to verify the final outcome of a test sequence. But once an operation is complete, the BBS typically outputs the main menu for the user to chose their next action. Thus, it's the *second to last* message in the output that is typically the most important for tests, so don't forget to check that instead of the last.

An example of this type of mistake is as follows:

In unit test:
```
last_call = self.mock_send_message.call_args_list[-1]
call_args, _ = last_call
self.assertIn("Congratulations! X wins!", call_args[0])
```

Which results in a test failure like:

```
AssertionError: 'Congratulations! X wins!' not found in '🎮Games Menu🎮\n[T]ic Tac Toe\nE[X]IT\n'
```

The actual code above should be:

```
last_call = self.mock_send_message.call_args_list[-2]
call_args, _ = last_call
self.assertIn("Congratulations! X wins!", call_args[0])
```