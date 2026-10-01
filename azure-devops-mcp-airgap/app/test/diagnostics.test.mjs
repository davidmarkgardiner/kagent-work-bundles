import { test } from 'node:test';
import assert from 'node:assert/strict';
import { diagnoseFailure } from '../diagnostics.mjs';

test('classifies credential, service, network and filesystem errors without leaking raw content', () => {
  const cases = [
    ['TF400813: The user private-user is not authorized', 'azure-devops-authentication'],
    ['403 Forbidden', 'azure-devops-permissions'],
    ['AADSTS50076: MFA required', 'entra-token'],
    ['getaddrinfo ENOTFOUND dev.azure.com', 'network'],
    ['PermissionError: Operation not permitted', 'local-permissions'],
    ['AzureCliCredential unavailable: please run az login', 'azure-cli-credential'],
    ['Unknown failure with private-user and private-details', 'unclassified-upstream-error'],
  ];
  for (const [message, category] of cases) {
    const failure = diagnoseFailure({ content: [{ type: 'text', text: message }] });
    assert.equal(failure.category, category);
    assert.ok(!JSON.stringify(failure).includes('private-user'));
    assert.ok(!JSON.stringify(failure).includes('private-details'));
  }
  assert.deepEqual(diagnoseFailure(new Error('AADSTS50076')).codes, ['AADSTS50076']);
});
