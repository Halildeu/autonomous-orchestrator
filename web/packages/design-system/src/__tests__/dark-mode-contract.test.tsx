// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { renderInDarkMode, cleanupDarkMode, expectNoBareColors } from './dark-mode-utils';

/* ------------------------------------------------------------------ */
/*  Imports — Primitives                                               */
/* ------------------------------------------------------------------ */
import {
  Button,
  Input,
  Select,
  Switch,
  Checkbox,
  Radio,
  RadioGroup,
  Dialog,
  Modal,
  Popover,
  Tooltip,
  Dropdown,
  Badge,
  Tag,
  Avatar,
  Alert,
  Spinner,
  Skeleton,
  Text,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Divider,
  IconButton,
  LinkInline,
  Stack,
  HStack,
  VStack,
  Drawer,
  Textarea,
} from '../primitives';

/* ------------------------------------------------------------------ */
/*  Imports — Components                                               */
/* ------------------------------------------------------------------ */
import {
  Tabs,
  Pagination,
  Steps,
  Breadcrumb,
  DatePicker,
  Combobox,
  Slider,
  Rating,
  SearchInput,
  Accordion,
  CommandPalette,
  InputNumber,
  Autocomplete,
  Upload,
  Timeline,
  Tree,
  Calendar,
  ColorPicker,
  ToastProvider,
  Segmented,
  Mentions,
  List,
  MenuBar,
  NavigationRail,
  ContextMenu,
  Transfer,
  Cascader,
  TimePicker,
  FormField,
  EmptyState,
  Descriptions,
  TableSimple,
  NotificationDrawer,
  DetailSectionTabs,
  TreeTable,
  JsonViewer,
  AnchorToc,
  ConfidenceBadge,
  BarChart,
  LineChart,
  PieChart,
  AreaChart,
  FloatButton,
  Watermark,
  QRCode,
  Carousel,
  AvatarGroup,
  EmptyErrorLoading,
} from '../components';

/* ------------------------------------------------------------------ */
/*  Imports — Patterns                                                 */
/* ------------------------------------------------------------------ */
import {
  PageHeader,
  PageLayout,
  DetailDrawer,
  FilterBar,
  SummaryStrip,
  MasterDetail,
  DetailSummary,
  FormDrawer,
  EntitySummaryBlock,
  ReportFilterPanel,
} from '../patterns';

/* ------------------------------------------------------------------ */
/*  jsdom polyfills & setup                                            */
/* ------------------------------------------------------------------ */
beforeAll(() => {
  // jsdom does not implement HTMLDialogElement.showModal / .close
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '');
    };
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute('open');
    };
  }

  // jsdom canvas getContext returns null — stub for Watermark & AG Charts
  const ctxStub = {
    font: '',
    measureText: () => ({ width: 50 }),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    strokeText: vi.fn(),
    strokeRect: vi.fn(),
    rotate: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    arc: vi.fn(),
    arcTo: vi.fn(),
    closePath: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    clip: vi.fn(),
    rect: vi.fn(),
    quadraticCurveTo: vi.fn(),
    bezierCurveTo: vi.fn(),
    setTransform: vi.fn(),
    getTransform: vi.fn().mockReturnValue({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
    resetTransform: vi.fn(),
    transform: vi.fn(),
    createLinearGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    createRadialGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    createPattern: vi.fn(),
    drawImage: vi.fn(),
    putImageData: vi.fn(),
    getImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
    createImageData: vi.fn(),
    setLineDash: vi.fn(),
    getLineDash: vi.fn().mockReturnValue([]),
    isPointInPath: vi.fn().mockReturnValue(false),
    isPointInStroke: vi.fn().mockReturnValue(false),
    ellipse: vi.fn(),
    lineWidth: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    miterLimit: 10,
    lineDashOffset: 0,
    strokeStyle: 'var(--text-primary)',
    fillStyle: 'var(--text-primary)',
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    shadowBlur: 0,
    shadowColor: 'rgba(0,0,0,0)',
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    textAlign: 'start',
    textBaseline: 'alphabetic',
    direction: 'inherit',
    imageSmoothingEnabled: true,
    canvas: { toDataURL: () => 'data:image/png;base64,AAAA', width: 300, height: 150 },
  };
  HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue(ctxStub) as unknown as typeof HTMLCanvasElement.prototype.getContext;

  // AG Charts requires Path2D in jsdom
  if (typeof globalThis.Path2D === 'undefined') {
    (globalThis as any).Path2D = class Path2D {
      constructor(_path?: string | Path2D) {}
      addPath() {}
      closePath() {}
      moveTo() {}
      lineTo() {}
      bezierCurveTo() {}
      quadraticCurveTo() {}
      arc() {}
      arcTo() {}
      ellipse() {}
      rect() {}
    };
  }
});

/*
 * Allowed bare-color exceptions:
 *
 * - "text-text-inverse" is intentionally used on filled/primary variants (white text on colored
 *   background is correct for both light and dark modes).
 * - ColorPicker uses inline background-color with rgb() for rendering actual color swatches
 *   — this is the component's functional output, not a themeable surface.
 */
const GLOBAL_ALLOW_LIST = [
  'text-text-inverse',
  'text-text-primary',
  // ECharts canvas container injects -webkit-tap-highlight-color inline — not controllable
  '-webkit-tap-highlight-color: rgb',
  'user-select: none',
];

/* ------------------------------------------------------------------ */
/*  Teardown                                                           */
/* ------------------------------------------------------------------ */
afterEach(() => {
  cleanup();
  cleanupDarkMode();
});

/* ================================================================== */
/*  Dark Mode Contract — Primitives                                    */
/* ================================================================== */
describe('Dark Mode Contract — Primitives', () => {
  it('Button renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Button>Click</Button>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Input renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Input placeholder="Type..." />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Textarea renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Textarea placeholder="Type..." />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Select renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Select options={[{ value: 'a', label: 'A' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Switch renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Switch />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Checkbox renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Checkbox label="Check" />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Radio renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Radio value="a" label="Option A" />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('RadioGroup renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <RadioGroup name="test" options={[{ value: 'a', label: 'A' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Dialog renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Dialog open onClose={() => {}} title="Test">
        <div>Content</div>
      </Dialog>
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Modal renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Modal open onClose={() => {}}>
        <div>Content</div>
      </Modal>
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Tooltip renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Tooltip content="Tooltip text">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Popover renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Popover content={<div>Popover content</div>}>
        <button>Open</button>
      </Popover>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Dropdown renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Dropdown items={[{ key: 'a', label: 'Action A' }]}>
        <button>Menu</button>
      </Dropdown>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Badge renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Badge>New</Badge>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Tag renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Tag>Label</Tag>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Avatar renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Avatar name="Test User" />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Alert renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Alert>Alert message</Alert>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Spinner renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Spinner />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Skeleton renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Skeleton />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Text renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Text>Hello</Text>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Card renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Card>
        <CardHeader>Header</CardHeader>
        <CardBody>Body</CardBody>
        <CardFooter>Footer</CardFooter>
      </Card>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Divider renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Divider />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('IconButton renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <IconButton label="action">
        <span>X</span>
      </IconButton>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('LinkInline renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<LinkInline href="#">Link</LinkInline>);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Stack renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Stack><div>A</div><div>B</div></Stack>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('HStack renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <HStack><div>A</div><div>B</div></HStack>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('VStack renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <VStack><div>A</div><div>B</div></VStack>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Drawer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Drawer open onClose={() => {}}>
        <div>Drawer content</div>
      </Drawer>
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });
});

/* ================================================================== */
/*  Dark Mode Contract — Components                                    */
/* ================================================================== */
describe('Dark Mode Contract — Components', () => {
  /* -- Navigation -- */

  it('Tabs renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Tabs items={[{ key: '1', label: 'Tab 1', children: <div>Content</div> }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Breadcrumb renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Breadcrumb items={[{ label: 'Home', href: '/' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Pagination renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Pagination total={100} />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Steps renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Steps items={[{ title: 'Step 1' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Timeline renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Timeline items={[{ key: 'e1', children: 'Event' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Disclosure -- */

  it('Accordion renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Accordion items={[{ value: '1', title: 'Item', content: <div>Content</div> }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Form -- */

  it('FormField renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <FormField label="Name"><Input /></FormField>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('SearchInput renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<SearchInput />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Feedback -- */

  it('ToastProvider renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <ToastProvider><div>App</div></ToastProvider>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('EmptyState renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <EmptyState title="Nothing here" />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('EmptyErrorLoading renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <EmptyErrorLoading mode="empty" />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Selection -- */

  it('Segmented renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Segmented items={[{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Menus -- */

  it('ContextMenu renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <ContextMenu items={[{ key: 'a', label: 'Action' }]}>
        <button>Right click</button>
      </ContextMenu>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('MenuBar renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <MenuBar items={[{ value: 'home', label: 'Home' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('NavigationRail renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <NavigationRail items={[{ value: 'home', label: 'Home' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Notification -- */

  it('NotificationDrawer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <NotificationDrawer open={false} items={[]} />
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Data Display -- */

  it('Descriptions renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Descriptions items={[{ key: 'a', label: 'Name', value: 'Alice' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('TableSimple renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <TableSimple
        columns={[{ key: 'name', header: 'Name' }]}
        rows={[{ name: 'Alice' }]}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Advanced Inputs -- */

  it('Slider renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Slider />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Rating renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Rating />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('DatePicker renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<DatePicker />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Calendar renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Calendar />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('TimePicker renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<TimePicker />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Upload renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<Upload />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Combobox renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Combobox options={[{ value: 'a', label: 'A' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('InputNumber renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<InputNumber />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Autocomplete renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Autocomplete options={[{ value: 'a', label: 'A' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('ColorPicker renders in dark mode without bare colors', () => {
    // ColorPicker uses inline background-color for color swatch rendering — this is functional,
    // not a themeable surface, so we allow inline rgb() on background-color.
    const { container } = renderInDarkMode(<ColorPicker />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, {
      allowList: [...GLOBAL_ALLOW_LIST, 'background-color: rgb'],
    });
  });

  it('Cascader renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Cascader options={[{ value: 'a', label: 'A' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Mentions renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Mentions options={[{ value: 'alice', label: 'Alice' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Data Structures -- */

  it('List renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <List items={[{ key: 'a', title: 'Item A' }, { key: 'b', title: 'Item B' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Transfer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Transfer dataSource={[]} targetKeys={[]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Tree renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Tree nodes={[{ key: '1', title: 'Node' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('TreeTable renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <TreeTable
        columns={[{ key: 'name', header: 'Name' }]}
        nodes={[{ key: '1', data: { name: 'Root' } }]}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('JsonViewer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <JsonViewer value={{ hello: 'world' }} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Search & Filter -- */

  it('CommandPalette renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <CommandPalette
        open={true}
        items={[{ id: 'a', title: 'Action' }]}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('AnchorToc renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <AnchorToc items={[{ id: 'section1', label: 'Section 1' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- AI / Domain -- */

  it('ConfidenceBadge renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <ConfidenceBadge level="high" />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Charts -- */

  it('BarChart renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <BarChart data={[{ label: 'A', value: 10 }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('LineChart renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <LineChart
        series={[{ name: 'S1', data: [10, 20] }]}
        labels={['Jan', 'Feb']}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('PieChart renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <PieChart data={[{ label: 'A', value: 10 }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('AreaChart renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <AreaChart
        series={[{ name: 'S1', data: [10, 20] }]}
        labels={['Jan', 'Feb']}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  /* -- Miscellaneous Components -- */

  it('FloatButton renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<FloatButton />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Watermark renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Watermark text="Draft"><div>Content</div></Watermark>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('QRCode renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<QRCode value="https://example.com" />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('Carousel renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <Carousel items={[
        { key: '1', content: <div>Slide 1</div> },
        { key: '2', content: <div>Slide 2</div> },
      ]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('AvatarGroup renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <AvatarGroup items={[{ key: 'a', name: 'Alice' }, { key: 'b', name: 'Bob' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('DetailSectionTabs renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <DetailSectionTabs
        tabs={[{ id: 'info', label: 'Info' }]}
        activeTabId="info"
        onTabChange={() => {}}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });
});

/* ================================================================== */
/*  Dark Mode Contract — Patterns                                      */
/* ================================================================== */
describe('Dark Mode Contract — Patterns', () => {
  it('PageHeader renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(<PageHeader title="Test Page" />);
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('PageLayout renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <PageLayout title="Layout"><div>Content</div></PageLayout>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('SummaryStrip renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <SummaryStrip items={[{ key: 'total', label: 'Total', value: '10' }]} />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('FilterBar renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <FilterBar><div>Filter controls</div></FilterBar>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('MasterDetail renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <MasterDetail
        master={<div>Master list</div>}
        detail={<div>Detail view</div>}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('DetailDrawer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <DetailDrawer open={false} onClose={() => {}} title="Detail">
        <div>Drawer content</div>
      </DetailDrawer>
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('FormDrawer renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <FormDrawer open={false} onClose={() => {}} title="Form">
        <div>Form content</div>
      </FormDrawer>
    );
    expect(container).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('EntitySummaryBlock renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <EntitySummaryBlock
        title="Test Entity"
        items={[{ key: 'name', label: 'Name', value: 'Alice' }]}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('DetailSummary renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <DetailSummary
        title="Summary"
        entity={{
          title: 'Entity',
          items: [{ key: 'name', label: 'Name', value: 'Alice' }],
        }}
      />
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });

  it('ReportFilterPanel renders in dark mode without bare colors', () => {
    const { container } = renderInDarkMode(
      <ReportFilterPanel><div>Filters</div></ReportFilterPanel>
    );
    expect(container.firstChild).toBeTruthy();
    expectNoBareColors(container, { allowList: GLOBAL_ALLOW_LIST });
  });
});
