import { Button, Form, Input } from 'antd';
import type { FormRule } from 'antd';
import { memo } from 'react';

import { nameErrorText } from './errorCopy';
import { nameErrorCodeOf, useCreateJob } from './hooks';

/** Same limit as the `name` column (backend `Job.name`, `max_length=255`). */
const NAME_MAX_LENGTH = 255;

type FormValues = Readonly<{ name?: string }>;

/**
 * Check a name the way the server will, and answer with the server's own
 * error code so both sources share one line of text each.
 *
 * Length is counted in code points (`[...text]`), as Django counts it;
 * `text.length` counts UTF-16 units and would refuse 200 emoji that the
 * server accepts.
 */
function nameErrorCode(value: unknown): 'blank' | 'max_length' | null {
  const name = typeof value === 'string' ? value.trim() : '';
  if (name === '') {
    return 'blank';
  }
  return [...name].length > NAME_MAX_LENGTH ? 'max_length' : null;
}

const NAME_RULES: FormRule[] = [
  {
    validator: (_rule, value: unknown) => {
      const code = nameErrorCode(value);
      return code === null ? Promise.resolve() : Promise.reject(new Error(nameErrorText(code)));
    },
  },
];

export type CreateJobFormProps = Readonly<{
  /** Called once the job exists; moves the list to its first page. */
  onCreated: () => void;
}>;

/**
 * One-line form that creates a job.
 *
 * The input's state lives in the form, so typing re-renders this component
 * only, never the table next to it.
 */
export const CreateJobForm = memo(function CreateJobForm({ onCreated }: CreateJobFormProps) {
  const [form] = Form.useForm<FormValues>();
  const { mutate: createJob, isPending } = useCreateJob(onCreated);

  const onFinish = (values: FormValues) => {
    // Enter can submit again while the first request is still out.
    if (isPending) {
      return;
    }
    createJob((values.name ?? '').trim(), {
      // Not resetFields(): that remounts the input and drops the keyboard focus,
      // and the next job name is most likely typed straight away.
      onSuccess: () => form.setFieldsValue({ name: '' }),
      onError: (error) => {
        // The server is the authority: it also refuses a name another job has.
        const code = nameErrorCodeOf(error);
        if (code !== null) {
          form.setFields([{ name: 'name', errors: [nameErrorText(code)] }]);
        }
      },
    });
  };

  // Validation runs on submit only, so an error from the last attempt would
  // otherwise stay under the input while the user is already correcting it.
  const clearNameError = () => {
    if (form.getFieldError('name').length > 0) {
      form.setFields([{ name: 'name', errors: [] }]);
    }
  };

  // TODO: the error text is tied to the input (aria-describedby, aria-invalid)
  //  but is not a live region, so a screen reader reads it on focus, not the
  //  moment it appears. Deferred: AntD renders the help text itself. Fix: pass
  //  `help` as an element with role="alert".
  return (
    <Form form={form} className="create-job-form" onFinish={onFinish} onValuesChange={clearNameError}>
      <Form.Item name="name" className="create-job-form__name" rules={NAME_RULES} validateTrigger="onSubmit">
        <Input aria-label="Job name" placeholder="New job name, e.g. Fluid Dynamics Simulation" autoComplete="off" />
      </Form.Item>
      <Button type="primary" htmlType="submit" loading={isPending}>
        Create job
      </Button>
    </Form>
  );
});
