import { expect, test } from '@playwright/test';

test.describe('DFMEA MVP acceptance flow', () => {
  test('runs the cooling fan draft, applies it, and pushes the fresh export payload', async ({
    page,
  }) => {
    await page.goto('/');

    await expect(page.getByText('Workspace ready')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('region', { name: 'Structure tree plugin' })).toContainText(
      'Working Tree',
    );

    await page.getByRole('button', { name: 'Start Run' }).click();
    await expect(page.getByText('Draft ready for review')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('list', { name: 'Runtime events' })).toContainText(
      'Run completed',
      { timeout: 60_000 },
    );

    await page.getByRole('button', { name: /Draft Review/ }).click();
    const draftReview = page.getByRole('region', { name: 'Draft review plugin' });
    await expect(draftReview).toContainText('Cooling fan controller DFMEA initial draft');
    await expect(draftReview.getByText('Nodes')).toBeVisible();
    await expect(page.getByLabel('Draft patches')).toContainText(
      'Engine Thermal Management System',
    );

    await draftReview.getByRole('button', { name: 'Apply' }).click();
    await expect(page.getByText('Applied revision 1')).toBeVisible({ timeout: 60_000 });

    const structure = page.getByRole('region', { name: 'Structure tree plugin' });
    await expect(structure).toContainText('Working Tree');
    await expect(page.getByLabel('Workspace structure')).toContainText(
      'Engine Thermal Management System',
    );

    await page.getByRole('button', { name: /API Push/ }).click();
    const apiPush = page.getByRole('region', { name: 'API Push plugin' });
    await expect(apiPush).toContainText('No push job');

    await apiPush.getByRole('button', { name: 'Validate' }).click();
    await expect(apiPush).toContainText('completed', { timeout: 60_000 });
    await expect(apiPush).toContainText('validate_only');
    await expect(apiPush).toContainText('api_push.validation.completed');

    await apiPush.getByRole('button', { name: 'Execute' }).click();
    await expect(apiPush).toContainText('execute', { timeout: 60_000 });
    await expect(apiPush).toContainText('accepted');
    await expect(apiPush).toContainText('api_push.execute.completed');
    await expect(apiPush).toContainText(/mature_fmea_/);
  });
});
